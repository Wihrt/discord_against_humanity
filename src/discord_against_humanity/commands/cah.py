"""Cards Against Humanity command module."""

import logging
from typing import Any

import discord
from discord import PermissionOverwrite
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
from discord_against_humanity.domain.game import MongoGame
from discord_against_humanity.domain.player import MongoPlayer
from discord_against_humanity.utils.embed import create_embed

logger = logging.getLogger("discord_against_humanity.commands")


class CardsAgainstHumanity(commands.Cog):
    """Implements Cards Against Humanity commands."""

    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the Cog.

        Args:
            bot: The Discord bot instance.
        """
        self.bot = bot
        self.mongo_client = self.bot.mongo  # type: ignore[attr-defined]

    # Commands
    # -------------------------------------------------------------------------

    @commands.command()
    @commands.guild_only()
    async def reminder(self, ctx: commands.Context) -> None:
        """Display the game rules reminder.

        Args:
            ctx: The invocation context.
        """
        await ctx.channel.send(embed=self._reminder())

    @commands.command()
    @commands.guild_only()
    @commands.check(no_game_exists)
    async def create(self, ctx: commands.Context) -> None:
        """Create a new game of Cards Against Humanity.

        Args:
            ctx: The invocation context.
        """
        permissions = self._default_permission(ctx.guild)  # type: ignore[arg-type]
        game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)  # type: ignore[attr-defined]
        game.guild = ctx.guild  # type: ignore[assignment]
        game.category = await ctx.guild.create_category("Cards Against Humanity")  # type: ignore[union-attr]
        game.board = await ctx.guild.create_text_channel(  # type: ignore[union-attr]
            "board", category=game.category, overwrites=permissions
        )
        await game.save()
        await ctx.message.delete()

    @commands.command()
    @commands.guild_only()
    @commands.check(game_exists)
    async def delete(self, ctx: commands.Context) -> None:
        """Delete a game of Cards Against Humanity.

        Args:
            ctx: The invocation context.
        """
        game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)  # type: ignore[attr-defined]
        players = await game.get_players()
        for player in players:
            await player.channel.delete()  # type: ignore[union-attr]
            await player.delete()
        await game.board.delete()  # type: ignore[union-attr]
        await game.category.delete()  # type: ignore[union-attr]
        await game.delete()
        await ctx.message.delete()

    @commands.command()
    @commands.guild_only()
    @commands.check(game_exists)
    @commands.check(is_not_player)
    async def join(self, ctx: commands.Context) -> None:
        """Join a Cards Against Humanity game.

        Args:
            ctx: The invocation context.
        """
        await ctx.message.delete()
        permissions = self._default_permission(ctx.guild)  # type: ignore[arg-type]
        user_permissions = PermissionOverwrite(
            read_messages=True, send_messages=True
        )
        game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)  # type: ignore[attr-defined]
        player = await MongoPlayer.create(ctx.bot, ctx.bot.mongo, user=ctx.author)  # type: ignore[attr-defined]
        name = "_".join(ctx.author.display_name.split())
        player.guild = ctx.guild  # type: ignore[assignment]
        player.user = ctx.author  # type: ignore[assignment]
        player.channel = await ctx.guild.create_text_channel(  # type: ignore[union-attr]
            name, category=game.category, overwrites=permissions
        )
        await game.board.set_permissions(  # type: ignore[union-attr]
            ctx.author, overwrite=user_permissions
        )
        await player.channel.set_permissions(ctx.author, overwrite=user_permissions)  # type: ignore[union-attr]
        await player.save()
        await game.add_player(player)
        await game.board.send(f"{ctx.author.mention} has joined the game!")  # type: ignore[union-attr]

    @commands.command()
    @commands.guild_only()
    @commands.check(game_exists)
    @commands.check(is_player)
    async def leave(self, ctx: commands.Context) -> None:
        """Leave the game.

        Args:
            ctx: The invocation context.
        """
        await ctx.message.delete()
        game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)  # type: ignore[attr-defined]
        player = await MongoPlayer.create(ctx.bot, ctx.bot.mongo, user=ctx.author)  # type: ignore[attr-defined]
        await game.delete_player(player)
        if player.document_id == game.tsar_id:
            await game.set_random_tsar()
            tsar = await game.get_tsar()
            await game.board.send(  # type: ignore[union-attr]
                f"{tsar.user.mention}! You're the tsar!"
            )
        await game.save()
        await player.channel.delete()  # type: ignore[union-attr]
        await player.delete()
        await game.board.send(f"{ctx.author.mention} has left the game!")  # type: ignore[union-attr]
        await game.board.set_permissions(ctx.author, overwrite=None)  # type: ignore[union-attr]

    @commands.command()
    @commands.guild_only()
    @commands.check(game_exists)
    @commands.check(game_not_playing)
    @commands.check(is_enough_players)
    async def start(self, ctx: commands.Context, points: int = 5) -> None:
        """Start the game.

        Args:
            ctx: The invocation context.
            points: Number of points required to win (default 5).
        """
        await ctx.message.delete()
        game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)  # type: ignore[attr-defined]
        game.playing = True
        game.points = points
        await game.save()
        await game.board.send("The game will start!")  # type: ignore[union-attr]
        await game.board.send(embed=self._reminder())  # type: ignore[union-attr]

        await game.set_random_tsar()
        is_score_max = await game.is_points_max()
        while game.playing and not is_score_max:
            tsar = await game.get_tsar()
            await game.board.send(f"{tsar.user.mention}! You're the tsar!")  # type: ignore[union-attr]
            question = await game.draw_black_card()
            await game.board.send(embed=question)  # type: ignore[union-attr]
            players = await game.get_players()
            for player in players:
                await player.channel.send(embed=question)  # type: ignore[union-attr]
                await player.draw_white_cards(game.white_cards_id)
            await game.wait_for_players_answers()
            proposals = await game.send_answers()
            await game.board.send(embed=proposals)  # type: ignore[union-attr]
            await tsar.channel.send(embed=proposals)  # type: ignore[union-attr]
            await game.wait_for_tsar_answer()
            await game.select_winner()
            await game.score()
            is_score_max = await game.is_points_max()
        await self.delete(ctx)

    @commands.command()
    @commands.guild_only()
    @commands.check(game_exists)
    @commands.check(game_playing)
    async def stop(self, ctx: commands.Context) -> None:
        """Stop the game.

        Args:
            ctx: The invocation context.
        """
        game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)  # type: ignore[attr-defined]
        game.playing = False
        await game.save()

    @commands.command()
    @commands.guild_only()
    @commands.check(game_exists)
    @commands.check(is_player)
    @commands.check(game_playing)
    @commands.check(from_user_channel)
    @commands.check(is_players_voting)
    @commands.check(is_not_tsar)
    async def vote(self, ctx: commands.Context, *answers: str) -> None:
        """Vote for answers as a player.

        Args:
            ctx: The invocation context.
            answers: Card numbers to vote for.
        """
        game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)  # type: ignore[attr-defined]
        player = await MongoPlayer.create(ctx.bot, ctx.bot.mongo, user=ctx.author)  # type: ignore[attr-defined]
        black_card = await game.get_black_card()
        try:
            int_answers = list(map(int, answers))
            if len(int_answers) != black_card.pick:
                await player.channel.send(  # type: ignore[union-attr]
                    f"You must provide {black_card.pick} answers. "
                    f"You provided {len(int_answers)} answers"
                )
            elif not all(i in range(1, 8) for i in int_answers):
                await player.channel.send(  # type: ignore[union-attr]
                    "Your answer(s) are not between 1 and 7"
                )
            else:
                await player.add_answers(int_answers)
                await game.board.send(f"{ctx.author.mention} has voted!")  # type: ignore[union-attr]
        except (TypeError, ValueError):
            await player.channel.send("Your answer is not an integer!")  # type: ignore[union-attr]

    @commands.command()
    @commands.guild_only()
    @commands.check(game_exists)
    @commands.check(is_player)
    @commands.check(game_playing)
    @commands.check(from_user_channel)
    @commands.check(is_tsar_voting)
    @commands.check(is_tsar)
    async def tsar(self, ctx: commands.Context, *, answers: str) -> None:
        """Vote for an answer as the tsar.

        Args:
            ctx: The invocation context.
            answers: The answer number to select.
        """
        game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)  # type: ignore[attr-defined]
        player = await MongoPlayer.create(ctx.bot, ctx.bot.mongo, user=ctx.author)  # type: ignore[attr-defined]
        try:
            answer = int(answers.split(" ")[0])
            if answer not in range(1, len(game.players_id)):  # type: ignore[arg-type]
                await player.channel.send(  # type: ignore[union-attr]
                    "Your answer is not in the acceptable range"
                )
            else:
                player.tsar_choice = answer
                await player.save()
                await game.board.send(f"{ctx.author.mention} has voted!")  # type: ignore[union-attr]
        except ValueError:
            await player.channel.send("Your answer is not an integer!")  # type: ignore[union-attr]

    @commands.command()
    @commands.guild_only()
    @commands.check(game_exists)
    @commands.check(game_playing)
    async def score(self, ctx: commands.Context) -> None:
        """Display the current scores.

        Args:
            ctx: The invocation context.
        """
        game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)  # type: ignore[attr-defined]
        await game.score()

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
                    f"3. Players vote  `Use {self.bot.command_prefix}"
                    "vote in your channel`\n"
                    f"4. Tsar vote  `Use {self.bot.command_prefix}"
                    "tsar in your channel`\n"
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
        permissions: dict[discord.Role | discord.Member, PermissionOverwrite] = {}
        permissions[guild.default_role] = PermissionOverwrite(read_messages=False)
        permissions[guild.me] = PermissionOverwrite(
            read_messages=True, send_messages=True
        )
        return permissions


async def setup(bot: commands.Bot) -> None:
    """Add the CardsAgainstHumanity cog to the bot.

    Args:
        bot: The Discord bot instance.
    """
    await bot.add_cog(CardsAgainstHumanity(bot))
