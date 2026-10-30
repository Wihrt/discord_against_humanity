"""Use cases: load the game, apply a rule, persist it, then notify players."""

import asyncio
import logging
from collections import defaultdict
from collections.abc import Sequence
from random import Random

from discord_against_humanity.application.ports import (
    CardDeck,
    GameNotifier,
    GameRepository,
)
from discord_against_humanity.domain.cards import BlackCard
from discord_against_humanity.domain.errors import (
    DeckExhaustedError,
    GameAlreadyExistsError,
    NoGameError,
)
from discord_against_humanity.domain.game import Game, Player

logger = logging.getLogger(__name__)


class GameService:
    """Entry point of the application layer, called by driving adapters.

    Every mutating use case runs under a per-guild lock so that concurrent
    interactions on the same game cannot overwrite each other.  This holds
    for a single bot process, which is how the bot is meant to be deployed.
    """

    def __init__(
        self,
        games: GameRepository,
        deck: CardDeck,
        notifier: GameNotifier,
        rng: Random | None = None,
    ) -> None:
        self._games = games
        self._deck = deck
        self._notifier = notifier
        self._rng = rng or Random()
        self._locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def find(self, guild_id: int) -> Game | None:
        return await self._games.get(guild_id)

    async def get(self, guild_id: int) -> Game:
        game = await self._games.get(guild_id)
        if game is None:
            raise NoGameError
        return game

    async def create(self, guild_id: int, category_id: int, board_id: int) -> Game:
        async with self._locks[guild_id]:
            if await self._games.get(guild_id) is not None:
                raise GameAlreadyExistsError
            game = Game(guild_id=guild_id, category_id=category_id, board_id=board_id)
            await self._games.save(game)
            return game

    async def delete(self, guild_id: int) -> Game:
        """Delete the game and return its last state so channels can be removed."""
        async with self._locks[guild_id]:
            game = await self.get(guild_id)
            await self._games.delete(guild_id)
            return game

    async def join(self, guild_id: int, user_id: int, channel_id: int) -> Player:
        async with self._locks[guild_id]:
            game = await self.get(guild_id)
            player = game.add_player(user_id, channel_id)
            await self._games.save(game)
        await self._notifier.player_joined(game, user_id)
        return player

    async def leave(self, guild_id: int, user_id: int) -> Player:
        async with self._locks[guild_id]:
            game = await self.get(guild_id)
            departure = game.remove_player(user_id, self._rng)
            restarted = departure.round_cancelled and await self._try_next_round(game)
            await self._games.save(game)

        await self._notifier.player_left(game, user_id)
        if departure.game_stopped:
            await self._notifier.game_stopped(game, "Not enough players left.")
        elif departure.round_cancelled:
            await self._notifier.round_cancelled(game, "A player left the round.")
            if restarted:
                await self._notifier.round_started(game)
            else:
                await self._notifier.game_stopped(game, "No cards left in the deck.")
        elif departure.judging_started:
            await self._notifier.judging_started(game)
        return departure.player

    async def start(self, guild_id: int, points: int, *, winner_becomes_czar: bool = False) -> Game:
        async with self._locks[guild_id]:
            game = await self.get(guild_id)
            game.start(points, winner_becomes_czar=winner_becomes_czar)
            await self._next_round(game)
            await self._games.save(game)
        await self._notifier.game_started(game)
        await self._notifier.round_started(game)
        return game

    async def stop(self, guild_id: int) -> Game:
        async with self._locks[guild_id]:
            game = await self.get(guild_id)
            game.stop()
            await self._games.save(game)
        await self._notifier.game_stopped(game, "The game was stopped.")
        return game

    async def submit_answers(self, guild_id: int, user_id: int, choices: Sequence[int]) -> None:
        async with self._locks[guild_id]:
            game = await self.get(guild_id)
            judging = game.submit_answers(user_id, choices, self._rng)
            await self._games.save(game)
        await self._notifier.answer_received(game, user_id)
        if judging:
            await self._notifier.judging_started(game)

    async def pick_winner(self, guild_id: int, user_id: int, choice: int) -> None:
        async with self._locks[guild_id]:
            game = await self.get(guild_id)
            result = game.pick_winner(user_id, choice)
            restarted = not result.game_over and await self._try_next_round(game)
            await self._games.save(game)

        await self._notifier.round_won(game, result)
        if result.game_over:
            await self._notifier.game_over(game, result.winner_id)
        elif restarted:
            await self._notifier.round_started(game)
        else:
            await self._notifier.game_stopped(game, "No cards left in the deck.")

    # Internals
    # -------------------------------------------------------------------------

    async def _next_round(self, game: Game) -> None:
        game.begin_round(await self._draw_playable_black_card(game), self._rng)
        # Dealt once the round is open: "Draw 2, Pick 3" cards only give
        # extra cards to the players who answer.
        for user_id, count in game.cards_needed().items():
            cards = await self._deck.draw_white_cards(count, game.white_cards_in_use())
            game.deal(user_id, cards)

    async def _draw_playable_black_card(self, game: Game) -> BlackCard:
        # Catalogs seeded by older versions may hold cards asking for more
        # answers than a hand can give: skip them.
        exclude = set(game.used_black_cards)
        while not (card := await self._deck.draw_black_card(exclude)).playable:
            logger.warning("Skipping unplayable black card %s (pick %d)", card.id, card.pick)
            exclude.add(card.id)
        return card

    async def _try_next_round(self, game: Game) -> bool:
        """Start the next round, or stop the game if the deck is exhausted."""
        try:
            await self._next_round(game)
        except DeckExhaustedError:
            logger.warning("Deck exhausted in guild %s, stopping the game", game.guild_id)
            game.stop()
            return False
        return True
