"""Slash commands: the driving adapter translating interactions into use cases.

Channel management (category, board, private channels) is a Discord
concern and lives here; game rules are delegated to :class:`GameService`.
"""

import logging
import re
from collections.abc import Iterable

import discord
from discord import PermissionOverwrite, app_commands
from discord.ext import commands

from discord_against_humanity.adapters.discord import messages
from discord_against_humanity.application.service import GameService
from discord_against_humanity.domain.errors import (
    AlreadyPlayerError,
    GameAlreadyExistsError,
    InvalidChoiceError,
)
from discord_against_humanity.domain.game import DEFAULT_POINTS, MAX_POINTS, MIN_POINTS

logger = logging.getLogger(__name__)

_CATEGORY_NAME = "Cards Against Humanity"
_BOARD_NAME = "board"
_MEMBER_ACCESS = PermissionOverwrite(view_channel=True, send_messages=True)


def _guild(interaction: discord.Interaction) -> discord.Guild:
    # Every command is guild_only, so this only guards against misuse.
    if interaction.guild is None:
        raise app_commands.NoPrivateMessage
    return interaction.guild


def _member(interaction: discord.Interaction) -> discord.Member:
    if not isinstance(interaction.user, discord.Member):
        raise app_commands.NoPrivateMessage
    return interaction.user


async def _set_board_access(
    guild: discord.Guild, board_id: int, member: discord.Member, *, allowed: bool
) -> None:
    board = guild.get_channel(board_id)
    if isinstance(board, discord.TextChannel):
        await board.set_permissions(member, overwrite=_MEMBER_ACCESS if allowed else None)


def _private_overwrites(
    guild: discord.Guild, *members: discord.Member | discord.User
) -> dict[discord.Role | discord.Member | discord.Object, PermissionOverwrite]:
    overwrites: dict[discord.Role | discord.Member | discord.Object, PermissionOverwrite] = {
        guild.default_role: PermissionOverwrite(view_channel=False),
        guild.me: PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
    }
    for member in members:
        overwrites[discord.Object(id=member.id)] = _MEMBER_ACCESS
    return overwrites


def _channel_name(member: discord.Member | discord.User) -> str:
    name = re.sub(r"[^\w-]+", "-", member.display_name.lower()).strip("-")
    return name or f"player-{member.id}"


def parse_choices(raw: str) -> list[int]:
    """Parse ``"2 5"`` or ``"2,5"`` into ``[2, 5]``."""
    try:
        return [int(token) for token in re.split(r"[\s,;]+", raw.strip()) if token]
    except ValueError:
        raise InvalidChoiceError(
            "Answers must be card numbers separated by spaces, e.g. `2 5`."
        ) from None


async def _delete_channels(guild: discord.Guild, channel_ids: Iterable[int]) -> None:
    for channel_id in channel_ids:
        channel = guild.get_channel(channel_id)
        if channel is None:
            continue
        try:
            await channel.delete(reason="Cards Against Humanity cleanup")
        except discord.NotFound:
            pass
        except discord.HTTPException:
            logger.warning("Could not delete channel %s", channel_id)


@app_commands.guild_only()
class CardsAgainstHumanity(commands.Cog):
    """Cards Against Humanity slash commands."""

    def __init__(self, service: GameService) -> None:
        self.service = service

    @app_commands.command(name="reminder", description="Display the game rules")
    async def reminder(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(embed=messages.rules_embed())

    @app_commands.command(name="create", description="Create a game in this server")
    async def create(self, interaction: discord.Interaction) -> None:
        guild = _guild(interaction)
        if await self.service.find(guild.id) is not None:
            raise GameAlreadyExistsError
        await interaction.response.defer(ephemeral=True, thinking=True)
        category = await guild.create_category(
            _CATEGORY_NAME, overwrites=_private_overwrites(guild)
        )
        board = await guild.create_text_channel(
            _BOARD_NAME, category=category, overwrites=_private_overwrites(guild)
        )
        try:
            await self.service.create(guild.id, category.id, board.id)
        except Exception:
            await _delete_channels(guild, [board.id, category.id])
            raise
        await interaction.followup.send(
            f"Game created in {board.mention}! Players can now `/join`.", ephemeral=True
        )

    @app_commands.command(name="delete", description="Delete the game and its channels")
    async def delete(self, interaction: discord.Interaction) -> None:
        guild = _guild(interaction)
        await interaction.response.defer(ephemeral=True, thinking=True)
        game = await self.service.delete(guild.id)
        await _delete_channels(
            guild,
            [
                *(p.channel_id for p in game.players.values()),
                game.board_id,
                game.category_id,
            ],
        )
        await interaction.followup.send("Game deleted.", ephemeral=True)

    @app_commands.command(name="join", description="Join the game")
    async def join(self, interaction: discord.Interaction) -> None:
        guild = _guild(interaction)
        user = _member(interaction)
        game = await self.service.get(guild.id)
        if game.has_player(user.id):
            raise AlreadyPlayerError
        await interaction.response.defer(ephemeral=True, thinking=True)

        category = guild.get_channel(game.category_id)
        channel = await guild.create_text_channel(
            _channel_name(user),
            category=category if isinstance(category, discord.CategoryChannel) else None,
            overwrites=_private_overwrites(guild, user),
        )
        try:
            await self.service.join(guild.id, user.id, channel.id)
        except Exception:
            await _delete_channels(guild, [channel.id])
            raise
        await _set_board_access(guild, game.board_id, user, allowed=True)
        await interaction.followup.send(
            f"You joined the game! Your cards will show up in {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(name="leave", description="Leave the game")
    async def leave(self, interaction: discord.Interaction) -> None:
        guild = _guild(interaction)
        await interaction.response.defer(ephemeral=True, thinking=True)
        game = await self.service.get(guild.id)
        player = await self.service.leave(guild.id, interaction.user.id)
        await _delete_channels(guild, [player.channel_id])
        await _set_board_access(guild, game.board_id, _member(interaction), allowed=False)
        await interaction.followup.send("You left the game.", ephemeral=True)

    @app_commands.command(name="start", description="Start the game")
    @app_commands.describe(points=f"Points needed to win (default {DEFAULT_POINTS})")
    async def start(
        self,
        interaction: discord.Interaction,
        points: app_commands.Range[int, MIN_POINTS, MAX_POINTS] = DEFAULT_POINTS,
    ) -> None:
        guild = _guild(interaction)
        await interaction.response.defer(ephemeral=True, thinking=True)
        game = await self.service.start(guild.id, points)
        await interaction.followup.send(
            f"Game started, head to {messages.channel_mention(game.board_id)}!",
            ephemeral=True,
        )

    @app_commands.command(name="stop", description="Stop the current game")
    async def stop(self, interaction: discord.Interaction) -> None:
        guild = _guild(interaction)
        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.service.stop(guild.id)
        await interaction.followup.send("Game stopped.", ephemeral=True)

    @app_commands.command(name="vote", description="Play card(s) from your hand")
    @app_commands.describe(answers="Card number(s) from your hand, e.g. `3` or `2 5`")
    async def vote(self, interaction: discord.Interaction, answers: str) -> None:
        guild = _guild(interaction)
        choices = parse_choices(answers)
        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.service.submit_answers(guild.id, interaction.user.id, choices)
        await interaction.followup.send("Answer recorded!", ephemeral=True)

    @app_commands.command(name="tsar", description="Pick the winning answer (tsar only)")
    @app_commands.describe(answer="Number of the winning answer")
    async def tsar(
        self, interaction: discord.Interaction, answer: app_commands.Range[int, 1]
    ) -> None:
        guild = _guild(interaction)
        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.service.pick_winner(guild.id, interaction.user.id, answer)
        await interaction.followup.send("Winner picked!", ephemeral=True)

    @app_commands.command(name="hand", description="Show the cards in your hand")
    async def hand(self, interaction: discord.Interaction) -> None:
        game = await self.service.get(_guild(interaction).id)
        player = game.player(interaction.user.id)
        await interaction.response.send_message(
            embed=messages.hand_embed(player.hand), ephemeral=True
        )

    @app_commands.command(name="score", description="Display the scoreboard")
    async def score(self, interaction: discord.Interaction) -> None:
        game = await self.service.get(_guild(interaction).id)
        await interaction.response.send_message(
            embed=messages.scoreboard_embed(game),
            allowed_mentions=discord.AllowedMentions.none(),
        )
