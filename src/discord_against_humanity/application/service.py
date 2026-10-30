"""Use cases: load the game, apply a rule, persist it, then notify players."""

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from functools import partial
from random import Random

from discord_against_humanity.application.ports import (
    CardDeck,
    GameNotifier,
    GameRepository,
    Scheduler,
)
from discord_against_humanity.domain.cards import BlackCard
from discord_against_humanity.domain.errors import (
    DeckExhaustedError,
    GameAlreadyExistsError,
    NoGameError,
)
from discord_against_humanity.domain.game import DEFAULT_TURN_SECONDS, Game, Player

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


class GameService:
    """Entry point of the application layer, called by driving adapters.

    Every mutating use case runs under a per-guild lock so that concurrent
    interactions on the same game cannot overwrite each other.  This holds
    for a single bot process, which is how the bot is meant to be deployed.

    Turn timers are armed through the scheduler each time a game is saved,
    from the deadline stored in the round; without a scheduler, rounds
    never time out.
    """

    def __init__(
        self,
        games: GameRepository,
        deck: CardDeck,
        notifier: GameNotifier,
        rng: Random | None = None,
        *,
        scheduler: Scheduler | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._games = games
        self._deck = deck
        self._notifier = notifier
        self._rng = rng or Random()
        self._scheduler = scheduler
        self._clock = clock
        self._locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def resume(self) -> None:
        """Re-arm the timers of the games in progress, e.g. after a restart."""
        for game in await self._games.all():
            self._arm_timer(game)

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
            await self._save(game)
            return game

    async def delete(self, guild_id: int) -> Game:
        """Delete the game and return its last state so channels can be removed."""
        async with self._locks[guild_id]:
            game = await self.get(guild_id)
            await self._games.delete(guild_id)
            if self._scheduler is not None:
                self._scheduler.cancel(guild_id)
            return game

    async def join(self, guild_id: int, user_id: int, channel_id: int) -> Player:
        async with self._locks[guild_id]:
            game = await self.get(guild_id)
            player = game.add_player(user_id, channel_id)
            await self._save(game)
        await self._notifier.player_joined(game, user_id)
        return player

    async def leave(self, guild_id: int, user_id: int) -> Player:
        async with self._locks[guild_id]:
            game = await self.get(guild_id)
            departure = game.remove_player(user_id, self._rng, self._clock())
            restarted = departure.round_cancelled and await self._try_next_round(game)
            await self._save(game)

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

    async def start(
        self,
        guild_id: int,
        points: int,
        *,
        winner_becomes_czar: bool = False,
        turn_seconds: int = DEFAULT_TURN_SECONDS,
    ) -> Game:
        async with self._locks[guild_id]:
            game = await self.get(guild_id)
            game.start(points, winner_becomes_czar=winner_becomes_czar, turn_seconds=turn_seconds)
            await self._next_round(game)
            await self._save(game)
        await self._notifier.game_started(game)
        await self._notifier.round_started(game)
        return game

    async def stop(self, guild_id: int) -> Game:
        async with self._locks[guild_id]:
            game = await self.get(guild_id)
            game.stop()
            await self._save(game)
        await self._notifier.game_stopped(game, "The game was stopped.")
        return game

    async def submit_answers(self, guild_id: int, user_id: int, choices: Sequence[int]) -> None:
        async with self._locks[guild_id]:
            game = await self.get(guild_id)
            judging = game.submit_answers(user_id, choices, self._rng, self._clock())
            await self._save(game)
        await self._notifier.answer_received(game, user_id)
        if judging:
            await self._notifier.judging_started(game)

    async def pick_winner(self, guild_id: int, user_id: int, choice: int) -> None:
        async with self._locks[guild_id]:
            game = await self.get(guild_id)
            result = game.pick_winner(user_id, choice)
            restarted = not result.game_over and await self._try_next_round(game)
            await self._save(game)

        await self._notifier.round_won(game, result)
        if result.game_over:
            await self._notifier.game_over(game, result.winner_id)
        elif restarted:
            await self._notifier.round_started(game)
        else:
            await self._notifier.game_stopped(game, "No cards left in the deck.")

    async def expire(self, guild_id: int) -> None:
        """Apply the turn timer: called by the scheduler at the deadline."""
        async with self._locks[guild_id]:
            game = await self._games.get(guild_id)
            if game is None:
                return
            timeout = game.expire(self._clock(), self._rng)
            if timeout is None:
                # Stale or early call: make sure the right deadline is armed.
                self._arm_timer(game)
                return
            restarted = timeout.round_cancelled and await self._try_next_round(game)
            await self._save(game)

        await self._notifier.round_timed_out(game, timeout)
        if timeout.judging_started:
            await self._notifier.judging_started(game)
        elif restarted:
            await self._notifier.round_started(game)
        else:
            await self._notifier.game_stopped(game, "No cards left in the deck.")

    # Internals
    # -------------------------------------------------------------------------

    async def _save(self, game: Game) -> None:
        await self._games.save(game)
        self._arm_timer(game)

    def _arm_timer(self, game: Game) -> None:
        if self._scheduler is None:
            return
        round_ = game.round
        if game.started and round_ is not None and round_.deadline is not None:
            self._scheduler.schedule(
                game.guild_id, round_.deadline, partial(self.expire, game.guild_id)
            )
        else:
            self._scheduler.cancel(game.guild_id)

    async def _next_round(self, game: Game) -> None:
        game.begin_round(await self._draw_playable_black_card(game), self._rng, self._clock())
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
