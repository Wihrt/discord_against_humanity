"""Discord implementation of the :class:`GameNotifier` port."""

import logging
from typing import Any

import discord

from discord_against_humanity.adapters.discord import messages
from discord_against_humanity.domain.game import Game, RoundResult

logger = logging.getLogger(__name__)


class DiscordNotifier:
    """Posts game events to the board and to players' private channels."""

    def __init__(self, client: discord.Client) -> None:
        self._client = client

    async def _send(self, channel_id: int, content: str | None = None, **kwargs: Any) -> None:
        channel = self._client.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self._client.fetch_channel(channel_id)
            except discord.HTTPException:
                logger.warning("Channel %s is unreachable", channel_id)
                return
        if not isinstance(channel, discord.abc.Messageable):
            logger.warning("Channel %s cannot receive messages", channel_id)
            return
        try:
            await channel.send(content, **kwargs)
        except discord.HTTPException:
            logger.exception("Could not send a message to channel %s", channel_id)

    async def player_joined(self, game: Game, user_id: int) -> None:
        await self._send(
            game.board_id,
            f"{messages.mention(user_id)} has joined the game! ({len(game.players)} players)",
        )

    async def player_left(self, game: Game, user_id: int) -> None:
        await self._send(game.board_id, f"{messages.mention(user_id)} has left the game.")

    async def game_started(self, game: Game) -> None:
        await self._send(
            game.board_id,
            f"The game starts! First to **{game.points_to_win}** points wins.",
            embed=messages.rules_embed(),
        )

    async def round_started(self, game: Game) -> None:
        round_ = game.round
        assert round_ is not None
        question = messages.question_embed(game)
        await self._send(
            game.board_id,
            f"{messages.mention(round_.tsar_id)} is the tsar for this round.",
            embed=question,
        )
        for player in game.players.values():
            if player.user_id == round_.tsar_id:
                await self._send(
                    player.channel_id,
                    "You are the **tsar** this round: wait for the answers, "
                    "then pick the best one with `/tsar`.",
                    embed=question,
                )
            elif player.user_id in round_.participants:
                await self._send(
                    player.channel_id,
                    f"Pick {round_.black_card.pick} card(s) with `/vote`.",
                    embeds=[question, messages.hand_embed(player.hand)],
                )
            else:
                await self._send(
                    player.channel_id,
                    "A round is in progress, you will play from the next one.",
                    embed=messages.hand_embed(player.hand),
                )

    async def answer_received(self, game: Game, user_id: int) -> None:
        round_ = game.round
        progress = ""
        if round_ is not None:
            progress = f" ({len(round_.answers)}/{len(round_.participants)})"
        await self._send(game.board_id, f"{messages.mention(user_id)} has answered.{progress}")

    async def judging_started(self, game: Game) -> None:
        assert game.round is not None
        proposals = messages.proposals_embed(game)
        tsar = game.players[game.round.tsar_id]
        await self._send(
            game.board_id,
            f"All answers are in! {messages.mention(tsar.user_id)}, pick the winner.",
            embed=proposals,
        )
        await self._send(tsar.channel_id, "Pick the winning answer with `/tsar`.", embed=proposals)

    async def round_cancelled(self, game: Game, reason: str) -> None:
        await self._send(game.board_id, f"Round cancelled: {reason}")

    async def round_won(self, game: Game, result: RoundResult) -> None:
        await self._send(
            game.board_id,
            f"{messages.mention(result.winner_id)} wins this round!",
            embed=messages.winner_embed(result),
        )

    async def game_over(self, game: Game, winner_id: int) -> None:
        await self._send(
            game.board_id,
            f":trophy: {messages.mention(winner_id)} wins the game! "
            "Use `/start` to play again or `/delete` to clean up.",
            embed=messages.scoreboard_embed(game, "Final scores"),
        )

    async def game_stopped(self, game: Game, reason: str) -> None:
        await self._send(
            game.board_id,
            f"Game stopped: {reason}",
            embed=messages.scoreboard_embed(game, "Final scores"),
        )
