"""Turn timer: domain rules, use cases and the asyncio scheduler."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from random import Random

import pytest

from discord_against_humanity.adapters.memory import InMemoryCardStore, InMemoryGameRepository
from discord_against_humanity.adapters.scheduler import AsyncioScheduler
from discord_against_humanity.adapters.valkey.serialization import game_from_dict, game_to_dict
from discord_against_humanity.application.service import GameService
from discord_against_humanity.domain.errors import InvalidTimerError
from discord_against_humanity.domain.game import Game, Phase
from tests.conftest import (
    BOARD,
    CATEGORY,
    GUILD,
    RecordingNotifier,
    make_black_cards,
    make_white_cards,
)
from tests.unit.test_game import QUESTION, hand

T0 = datetime(2026, 1, 1, 20, 0, tzinfo=UTC)
TURN = timedelta(seconds=60)


def timed_game(players: int = 4) -> Game:
    game = Game(guild_id=1, category_id=2, board_id=3)
    for uid in range(1, players + 1):
        game.add_player(uid, channel_id=100 + uid)
        game.deal(uid, hand(uid))
    game.start(points=5, turn_seconds=60)
    game.next_czar_id = 1
    game.begin_round(QUESTION, Random(0), T0)
    return game


class TestDomain:
    def test_round_deadline(self) -> None:
        game = timed_game()
        assert game.round is not None
        assert game.round.deadline == T0 + TURN

    def test_no_clock_or_no_timer_means_no_deadline(self) -> None:
        game = Game(guild_id=1, category_id=2, board_id=3)
        for uid in (1, 2, 3):
            game.add_player(uid, channel_id=uid)
        game.start(points=5, turn_seconds=0)
        assert game.begin_round(QUESTION, Random(0), T0).deadline is None

    @pytest.mark.parametrize("seconds", [5, 601])
    def test_timer_bounds(self, seconds: int) -> None:
        game = Game(guild_id=1, category_id=2, board_id=3)
        for uid in (1, 2, 3):
            game.add_player(uid, channel_id=uid)
        with pytest.raises(InvalidTimerError):
            game.start(points=5, turn_seconds=seconds)

    def test_judging_gets_its_own_deadline(self) -> None:
        game = timed_game(players=3)
        later = T0 + timedelta(seconds=20)
        game.submit_answers(2, [1], Random(0), later)
        game.submit_answers(3, [1], Random(0), later)
        assert game.round is not None
        assert game.round.deadline == later + TURN

    def test_nothing_happens_before_the_deadline(self) -> None:
        game = timed_game()
        assert game.expire(T0 + TURN - timedelta(seconds=1), Random(0)) is None
        assert game.phase is Phase.ANSWERING

    def test_late_players_sit_the_round_out(self) -> None:
        game = timed_game(players=4)
        game.submit_answers(2, [1], Random(0), T0)
        game.submit_answers(3, [1], Random(0), T0)

        timeout = game.expire(T0 + TURN, Random(0))

        assert timeout is not None
        assert timeout.late == (4,)
        assert timeout.judging_started
        assert game.phase is Phase.JUDGING
        assert sorted(uid for uid, _ in game.proposals()) == [2, 3]
        assert game.round is not None
        assert game.round.deadline == T0 + 2 * TURN
        assert len(game.players[4].hand) == len(hand(4)), "late cards stay in hand"

    def test_round_skipped_when_nobody_answers(self) -> None:
        game = timed_game()
        timeout = game.expire(T0 + TURN, Random(0))
        assert timeout is not None
        assert timeout.round_cancelled
        assert timeout.late == (2, 3, 4)
        assert game.round is None
        assert game.next_czar_id == 2

    def test_slow_card_czar_skips_the_round(self) -> None:
        game = timed_game(players=3)
        game.submit_answers(2, [1], Random(0), T0)
        game.submit_answers(3, [1], Random(0), T0)

        timeout = game.expire(T0 + 2 * TURN, Random(0))

        assert timeout is not None
        assert timeout.phase is Phase.JUDGING
        assert timeout.late == (1,)
        assert game.round is None
        assert game.next_czar_id == 2
        assert all(len(game.players[uid].hand) == len(hand(uid)) for uid in (2, 3))
        assert all(p.score == 0 for p in game.players.values())

    def test_deadline_survives_serialization(self) -> None:
        game = timed_game()
        restored = game_from_dict(json.loads(json.dumps(game_to_dict(game))))
        assert restored == game


class FakeScheduler:
    def __init__(self) -> None:
        self.pending: dict[int, tuple[datetime, Callable[[], Awaitable[None]]]] = {}

    def schedule(self, key: int, when: datetime, action: Callable[[], Awaitable[None]]) -> None:
        self.pending[key] = (when, action)

    def cancel(self, key: int) -> None:
        self.pending.pop(key, None)

    async def fire(self, key: int) -> None:
        _, action = self.pending.pop(key)
        await action()


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def scheduler() -> FakeScheduler:
    return FakeScheduler()


@pytest.fixture
def timed_service(
    games: InMemoryGameRepository,
    notifier: RecordingNotifier,
    scheduler: FakeScheduler,
    clock: Clock,
) -> GameService:
    deck = InMemoryCardStore(make_black_cards(), make_white_cards(), rng=Random(1))
    return GameService(games, deck, notifier, Random(1), scheduler=scheduler, clock=clock)


async def started(service: GameService) -> Game:
    await service.create(GUILD, CATEGORY, BOARD)
    for uid in (1, 2, 3, 4):
        await service.join(GUILD, uid, channel_id=100 + uid)
    return await service.start(GUILD, points=5, turn_seconds=60)


class TestService:
    async def test_start_arms_the_timer(
        self, timed_service: GameService, scheduler: FakeScheduler
    ) -> None:
        await started(timed_service)
        assert scheduler.pending[GUILD][0] == T0 + TURN

    async def test_last_answer_rearms_for_judging(
        self, timed_service: GameService, scheduler: FakeScheduler, clock: Clock
    ) -> None:
        game = await started(timed_service)
        assert game.round is not None
        clock.now = T0 + timedelta(seconds=30)
        for uid in game.round.participants:
            await timed_service.submit_answers(GUILD, uid, [1])
        assert scheduler.pending[GUILD][0] == clock.now + TURN

    async def test_stop_and_delete_disarm(
        self, timed_service: GameService, scheduler: FakeScheduler
    ) -> None:
        await started(timed_service)
        await timed_service.stop(GUILD)
        assert GUILD not in scheduler.pending
        await timed_service.start(GUILD, points=5, turn_seconds=60)
        await timed_service.delete(GUILD)
        assert GUILD not in scheduler.pending

    async def test_answer_timeout_moves_on_to_judging(
        self,
        timed_service: GameService,
        scheduler: FakeScheduler,
        notifier: RecordingNotifier,
        clock: Clock,
    ) -> None:
        game = await started(timed_service)
        assert game.round is not None
        early = game.round.participants[0]
        await timed_service.submit_answers(GUILD, early, [1])

        clock.now = T0 + TURN
        await scheduler.fire(GUILD)

        game = await timed_service.get(GUILD)
        assert game.phase is Phase.JUDGING
        assert [uid for uid, _ in game.proposals()] == [early]
        assert notifier.names()[-2:] == ["round_timed_out", "judging_started"]
        assert scheduler.pending[GUILD][0] == clock.now + TURN

    async def test_czar_timeout_starts_a_new_round(
        self,
        timed_service: GameService,
        scheduler: FakeScheduler,
        notifier: RecordingNotifier,
        clock: Clock,
    ) -> None:
        game = await started(timed_service)
        assert game.round is not None
        czar = game.round.czar_id
        for uid in game.round.participants:
            await timed_service.submit_answers(GUILD, uid, [1])

        clock.now = T0 + 2 * TURN
        await scheduler.fire(GUILD)

        game = await timed_service.get(GUILD)
        assert game.round is not None
        assert game.round.czar_id != czar
        assert game.phase is Phase.ANSWERING
        assert notifier.names()[-2:] == ["round_timed_out", "round_started"]

    async def test_early_call_changes_nothing(
        self,
        timed_service: GameService,
        scheduler: FakeScheduler,
        notifier: RecordingNotifier,
    ) -> None:
        await started(timed_service)
        before = notifier.names()
        await scheduler.fire(GUILD)
        assert notifier.names() == before
        assert scheduler.pending[GUILD][0] == T0 + TURN, "re-armed"

    async def test_resume_rearms_saved_deadlines(
        self,
        games: InMemoryGameRepository,
        notifier: RecordingNotifier,
        clock: Clock,
    ) -> None:
        deck = InMemoryCardStore(make_black_cards(), make_white_cards())
        before = GameService(games, deck, notifier, scheduler=FakeScheduler(), clock=clock)
        await started(before)

        # The bot restarts: a new service and scheduler on the same storage.
        scheduler = FakeScheduler()
        after = GameService(games, deck, notifier, scheduler=scheduler, clock=clock)
        await after.resume()
        assert scheduler.pending[GUILD][0] == T0 + TURN


class TestAsyncioScheduler:
    async def test_runs_the_action(self) -> None:
        scheduler = AsyncioScheduler()
        done = asyncio.Event()

        async def action() -> None:
            done.set()

        scheduler.schedule(1, datetime.now(UTC), action)
        await asyncio.wait_for(done.wait(), timeout=1)
        assert scheduler.pending() == set()

    async def test_rescheduling_replaces_the_pending_action(self) -> None:
        scheduler = AsyncioScheduler()
        calls: list[str] = []

        async def first() -> None:
            calls.append("first")

        async def second() -> None:
            calls.append("second")

        scheduler.schedule(1, datetime.now(UTC) + timedelta(milliseconds=50), first)
        scheduler.schedule(1, datetime.now(UTC) + timedelta(milliseconds=10), second)
        await asyncio.sleep(0.1)
        assert calls == ["second"]

    async def test_action_can_schedule_its_successor(self) -> None:
        scheduler = AsyncioScheduler()
        calls: list[int] = []

        async def action() -> None:
            calls.append(len(calls))
            if len(calls) < 3:
                scheduler.schedule(1, datetime.now(UTC), action)

        scheduler.schedule(1, datetime.now(UTC), action)
        await asyncio.sleep(0.05)
        assert calls == [0, 1, 2]

    async def test_close_cancels_everything(self) -> None:
        scheduler = AsyncioScheduler()
        calls: list[int] = []

        async def action() -> None:
            calls.append(1)

        scheduler.schedule(1, datetime.now(UTC) + timedelta(seconds=10), action)
        await scheduler.close()
        assert scheduler.pending() == set()
        assert calls == []
