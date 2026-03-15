"""Cards Against Humanity slash command module."""

import logging
from typing import Any

import discord
from discord import PermissionOverwrite, app_commands
from discord.ext import commands

from discord_against_humanity.checks.game_checks import (
    from_user_channel,
    game_exists,
    game_not_playing,
    game_playing,
    is_enough_players,
    is_not_player,
    is_not_tsar,
    is_player,
    is_players_voting,
    is_tsar,
    is_tsar_voting,
    no_game_exists,
)
from discord_against_humanity.domain.game import ValkeyGame
from discord_against_humanity.domain.player import ValkeyPlayer
from discord_against_humanity.utils.embed import create_embed

logger = logging.getLogger("discord_against_humanity.commands")


class CardsAgainstHumanity(commands.Cog):
    """Implements Cards Against Humanity slash commands."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the Cog.

        Args:
            bot: The Discord bot instance.
        """
        self.bot = bot
        self.valkey_client = self.bot.valkey  # type: ignore[attr-defined]

    # Slash Commands
    # -------------------------------------------------------------------------

    @app_commands.command(
        name="reminder", description="Display the game rules reminder"
    )
    @app_commands.guild_only()
    async def reminder(self, interaction: discord.Interaction) -> None:
        """Display the game rules reminder.

        Args:
            interaction: The Discord interaction.
        """
        await interaction.response.send_message(embed=self._reminder())

    @app_commands.command(
        name="create",
        description="Create a new game of Cards Against Humanity",
    )
    @app_commands.guild_only()
    @app_commands.check(no_game_exists)
    async def create(self, interaction: discord.Interaction) -> None:
        """Create a new game of Cards Against Humanity.

        Args:
            interaction: The Discord interaction.
        """
        assert interaction.guild is not None
        permissions = self._default_permission(interaction.guild)
        game = await ValkeyGame.create(
            self.bot, self.bot.valkey, interaction.guild  # type: ignore[attr-defined]
        )
        game.guild = interaction.guild
        game.category = await interaction.guild.create_category(
            "Cards Against Humanity"
        )
        game.board = await interaction.guild.create_text_channel(
            "board", category=game.category, overwrites=permissions
        )
        await game.save()
        await interaction.response.send_message(
            "Game created! Use `/join` to join.", ephemeral=True
        )

    @app_commands.command(
        name="delete",
        description="Delete the current game of Cards Against Humanity",
    )
    @app_commands.guild_only()
    @app_commands.check(game_exists)
    async def delete_game(self, interaction: discord.Interaction) -> None:
        """Delete a game of Cards Against Humanity.

        Args:
            interaction: The Discord interaction.
        """
        assert interaction.guild is not None
        await interaction.response.defer(ephemeral=True)
        game = await ValkeyGame.create(
            self.bot, self.bot.valkey, interaction.guild  # type: ignore[attr-defined]
        )
        players = await game.get_players()
        for player in players:
            if player.channel is not None:
                await player.channel.delete()
            await player.delete()
        if game.board is not None:
            await game.board.delete()
        if game.category is not None:
            await game.category.delete()
        await game.delete()
        await interaction.followup.send("Game deleted.", ephemeral=True)

    @app_commands.command(
        name="join", description="Join the Cards Against Humanity game"
    )
    @app_commands.guild_only()
    @app_commands.check(game_exists)
    @app_commands.check(is_not_player)
    async def join(self, interaction: discord.Interaction) -> None:
        """Join a Cards Against Humanity game.

        Args:
            interaction: The Discord interaction.
        """
        assert interaction.guild is not None
        await interaction.response.defer(ephemeral=True)
        permissions = self._default_permission(interaction.guild)
        user_permissions = PermissionOverwrite(
            read_messages=True, send_messages=True
        )
        game = await ValkeyGame.create(
            self.bot, self.bot.valkey, interaction.guild  # type: ignore[attr-defined]
        )
        player = await ValkeyPlayer.create(
            self.bot,
            self.bot.valkey,  # type: ignore[attr-defined]
            user=interaction.user,
            guild=interaction.guild,
        )
        name = "_".join(interaction.user.display_name.split())
        player.guild = interaction.guild
        player.user = interaction.user  # type: ignore[assignment]
        player.channel = await interaction.guild.create_text_channel(
            name, category=game.category, overwrites=permissions
        )
        await game.board.set_permissions(  # type: ignore[union-attr]
            interaction.user, overwrite=user_permissions
        )
        await player.channel.set_permissions(
            interaction.user, overwrite=user_permissions
        )
        await player.save()
        await game.add_player(player)
        await game.board.send(  # type: ignore[union-attr]
            f"{interaction.user.mention} has joined the game!"
        )
        await interaction.followup.send("You joined the game!", ephemeral=True)

    @app_commands.command(
        name="leave", description="Leave the Cards Against Humanity game"
    )
    @app_commands.guild_only()
    @app_commands.check(game_exists)
    @app_commands.check(is_player)
    async def leave(self, interaction: discord.Interaction) -> None:
        """Leave the game.

        Args:
            interaction: The Discord interaction.
        """
        assert interaction.guild is not None
        await interaction.response.defer(ephemeral=True)
        game = await ValkeyGame.create(
            self.bot, self.bot.valkey, interaction.guild  # type: ignore[attr-defined]
        )
        player = await ValkeyPlayer.create(
            self.bot,
            self.bot.valkey,  # type: ignore[attr-defined]
            user=interaction.user,
            guild=interaction.guild,
        )
        await game.delete_player(player)
        if player.document_id == game.tsar_id and game.players_id:
            await game.set_random_tsar()
            tsar = await game.get_tsar()
            await game.board.send(  # type: ignore[union-attr]
                f"{tsar.user.mention}! You're the tsar!"
            )
        await game.save()
        if player.channel is not None:
            await player.channel.delete()
        await player.delete()
        await game.board.send(  # type: ignore[union-attr]
            f"{interaction.user.mention} has left the game!"
        )
        await game.board.set_permissions(  # type: ignore[union-attr]
            interaction.user, overwrite=None
        )
        await interaction.followup.send("You left the game.", ephemeral=True)

    @app_commands.command(name="start", description="Start the game")
    @app_commands.describe(points="Number of points to win (default 5)")
    @app_commands.guild_only()
    @app_commands.check(game_exists)
    @app_commands.check(game_not_playing)
    @app_commands.check(is_enough_players)
    async def start(
        self, interaction: discord.Interaction, points: int = 5
    ) -> None:
        """Start the game.

        Args:
            interaction: The Discord interaction.
            points: Number of points required to win (default 5).
        """
        assert interaction.guild is not None
        await interaction.response.defer(ephemeral=True)
        game = await ValkeyGame.create(
            self.bot, self.bot.valkey, interaction.guild  # type: ignore[attr-defined]
        )
        game.playing = True
        game.points = points
        await game.save()
        await game.board.send("The game will start!")  # type: ignore[union-attr]
        await game.board.send(embed=self._reminder())  # type: ignore[union-attr]

        await game.set_random_tsar()
        is_score_max = await game.is_points_max()
        while game.playing and not is_score_max:
            await game.get(game.document_id)
            if not game.playing:
                break
            tsar = await game.get_tsar()
            await game.board.send(  # type: ignore[union-attr]
                f"{tsar.user.mention}! You're the tsar!"
            )
            question = await game.draw_black_card()
            await game.board.send(embed=question)  # type: ignore[union-attr]
            players = await game.get_players()
            for player in players:
                if player.channel is not None:
                    await player.channel.send(embed=question)
                await player.draw_white_cards(game.white_cards_id)
            await game.wait_for_players_answers()
            proposals = await game.send_answers()
            await game.board.send(embed=proposals)  # type: ignore[union-attr]
            if tsar.channel is not None:
                await tsar.channel.send(embed=proposals)
            await game.wait_for_tsar_answer()
            await game.select_winner()
            await game.score()
            is_score_max = await game.is_points_max()
        await self._cleanup_game(interaction)
        await interaction.followup.send("Game over!", ephemeral=True)

    @app_commands.command(name="stop", description="Stop the current game")
    @app_commands.guild_only()
    @app_commands.check(game_exists)
    @app_commands.check(game_playing)
    async def stop(self, interaction: discord.Interaction) -> None:
        """Stop the game.

        Args:
            interaction: The Discord interaction.
        """
        assert interaction.guild is not None
        game = await ValkeyGame.create(
            self.bot, self.bot.valkey, interaction.guild  # type: ignore[attr-defined]
        )
        game.playing = False
        await game.save()
        await interaction.response.send_message("Game stopped.", ephemeral=True)

    @app_commands.command(
        name="vote", description="Vote for your answer(s) as a player"
    )
    @app_commands.describe(
        answers="Card number(s) to vote for, space-separated"
    )
    @app_commands.guild_only()
    @app_commands.check(game_exists)
    @app_commands.check(is_player)
    @app_commands.check(game_playing)
    @app_commands.check(from_user_channel)
    @app_commands.check(is_players_voting)
    @app_commands.check(is_not_tsar)
    async def vote(
        self, interaction: discord.Interaction, answers: str
    ) -> None:
        """Vote for answers as a player.

        Args:
            interaction: The Discord interaction.
            answers: Space-separated card numbers to vote for.
        """
        assert interaction.guild is not None
        game = await ValkeyGame.create(
            self.bot, self.bot.valkey, interaction.guild  # type: ignore[attr-defined]
        )
        player = await ValkeyPlayer.create(
            self.bot,
            self.bot.valkey,  # type: ignore[attr-defined]
            user=interaction.user,
            guild=interaction.guild,
        )
        black_card = await game.get_black_card()
        try:
            int_answers = list(map(int, answers.split()))
            if len(int_answers) != black_card.pick:
                await interaction.response.send_message(
                    f"You must provide {black_card.pick} answers. "
                    f"You provided {len(int_answers)} answers.",
                    ephemeral=True,
                )
            elif not all(i in range(1, 8) for i in int_answers):
                await interaction.response.send_message(
                    "Your answer(s) are not between 1 and 7.", ephemeral=True
                )
            else:
                await player.add_answers(int_answers)
                await game.board.send(  # type: ignore[union-attr]
                    f"{interaction.user.mention} has voted!"
                )
                await interaction.response.send_message(
                    "Vote recorded!", ephemeral=True
                )
        except (TypeError, ValueError):
            await interaction.response.send_message(
                "Your answer is not a valid integer!", ephemeral=True
            )

    @app_commands.command(
        name="tsar", description="Vote for an answer as the tsar"
    )
    @app_commands.describe(answer="The answer number to select")
    @app_commands.guild_only()
    @app_commands.check(game_exists)
    @app_commands.check(is_player)
    @app_commands.check(game_playing)
    @app_commands.check(from_user_channel)
    @app_commands.check(is_tsar_voting)
    @app_commands.check(is_tsar)
    async def tsar(self, interaction: discord.Interaction, answer: int) -> None:
        """Vote for an answer as the tsar.

        Args:
            interaction: The Discord interaction.
            answer: The answer number to select.
        """
        assert interaction.guild is not None
        game = await ValkeyGame.create(
            self.bot, self.bot.valkey, interaction.guild  # type: ignore[attr-defined]
        )
        player = await ValkeyPlayer.create(
            self.bot,
            self.bot.valkey,  # type: ignore[attr-defined]
            user=interaction.user,
            guild=interaction.guild,
        )
        if answer not in range(1, len(game.players_id)):  # type: ignore[arg-type]
            await interaction.response.send_message(
                "Your answer is not in the acceptable range.", ephemeral=True
            )
        else:
            player.tsar_choice = answer
            await player.save()
            await game.board.send(  # type: ignore[union-attr]
                f"{interaction.user.mention} has voted!"
            )
            await interaction.response.send_message(
                "Tsar vote recorded!", ephemeral=True
            )

    @app_commands.command(
        name="score", description="Display the current scores"
    )
    @app_commands.guild_only()
    @app_commands.check(game_exists)
    @app_commands.check(game_playing)
    async def score(self, interaction: discord.Interaction) -> None:
        """Display the current scores.

        Args:
            interaction: The Discord interaction.
        """
        assert interaction.guild is not None
        game = await ValkeyGame.create(
            self.bot, self.bot.valkey, interaction.guild  # type: ignore[attr-defined]
        )
        await game.score()
        await interaction.response.send_message(
            "Score displayed on the board.", ephemeral=True
        )

    # Helpers
    # -------------------------------------------------------------------------

    def _reminder(self) -> discord.Embed:
        """Build the game rules reminder embed.

        Returns:
            A Discord Embed with the game rules.
        """
        embed: dict[str, Any] = {
            "fields": {
                "name": "Reminder",
                "inline": False,
                "value": (
                    "Course of the game:\n"
                    "1. A black card (question) is picked\n"
                    "2. Players pick white cards (answers)\n"
                    "3. Players vote — Use `/vote` in your channel\n"
                    "4. Tsar votes — Use `/tsar` in your channel\n"
                    "5. Deciding winner and go back to start"
                ),
            }
        }
        return create_embed(embed)

    def _default_permission(
        self, guild: discord.Guild
    ) -> dict[discord.Role | discord.Member, PermissionOverwrite]:
        """Create default channel permissions.

        Args:
            guild: The Discord guild.

        Returns:
            A permissions overwrites mapping.
        """
        permissions: dict[
            discord.Role | discord.Member, PermissionOverwrite
        ] = {}
        permissions[guild.default_role] = PermissionOverwrite(
            read_messages=False
        )
        permissions[guild.me] = PermissionOverwrite(
            read_messages=True, send_messages=True
        )
        return permissions

    async def _cleanup_game(
        self, interaction: discord.Interaction
    ) -> None:
        """Clean up game resources after a game ends.

        Args:
            interaction: The Discord interaction.
        """
        assert interaction.guild is not None
        game = await ValkeyGame.create(
            self.bot, self.bot.valkey, interaction.guild  # type: ignore[attr-defined]
        )
        players = await game.get_players()
        for player in players:
            if player.channel is not None:
                await player.channel.delete()
            await player.delete()
        if game.board is not None:
            await game.board.delete()
        if game.category is not None:
            await game.category.delete()
        await game.delete()


async def setup(bot: commands.Bot) -> None:
    """Add the CardsAgainstHumanity cog to the bot.

    Args:
        bot: The Discord bot instance.
    """
    await bot.add_cog(CardsAgainstHumanity(bot))
