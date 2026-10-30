from random import Random
from typing import Any

import pytest

from discord_against_humanity.adapters.memory import InMemoryCardStore, InMemoryGameRepository
from discord_against_humanity.application.service import GameService
from discord_against_humanity.domain.cards import BlackCard, WhiteCard
from discord_against_humanity.domain.game import Game, RoundResult

GUILD = 1000
CATEGORY = 2000
BOARD = 2001


def make_black_cards(count: int = 20, pick: int = 1) -> list[BlackCard]:
    return [BlackCard(id=f"b{i}", text=f"Question {i}: _.", pick=pick) for i in range(count)]


def make_white_cards(count: int = 200) -> list[WhiteCard]:
    return [WhiteCard(id=f"w{i}", text=f"Answer {i}.") for i in range(count)]


class RecordingNotifier:
    """Test double for the GameNotifier port: records every event."""

    def __init__(self) -> None:
        self.events: list[tuple[str, Any]] = []

    def names(self) -> list[str]:
        return [name for name, _ in self.events]

    async def player_joined(self, game: Game, user_id: int) -> None:
        self.events.append(("player_joined", user_id))

    async def player_left(self, game: Game, user_id: int) -> None:
        self.events.append(("player_left", user_id))

    async def game_started(self, game: Game) -> None:
        self.events.append(("game_started", None))

    async def round_started(self, game: Game) -> None:
        assert game.round is not None
        self.events.append(("round_started", game.round.tsar_id))

    async def answer_received(self, game: Game, user_id: int) -> None:
        self.events.append(("answer_received", user_id))

    async def judging_started(self, game: Game) -> None:
        self.events.append(("judging_started", None))

    async def round_cancelled(self, game: Game, reason: str) -> None:
        self.events.append(("round_cancelled", reason))

    async def round_won(self, game: Game, result: RoundResult) -> None:
        self.events.append(("round_won", result.winner_id))

    async def game_over(self, game: Game, winner_id: int) -> None:
        self.events.append(("game_over", winner_id))

    async def game_stopped(self, game: Game, reason: str) -> None:
        self.events.append(("game_stopped", reason))


@pytest.fixture
def rng() -> Random:
    return Random(42)


@pytest.fixture
def games() -> InMemoryGameRepository:
    return InMemoryGameRepository()


@pytest.fixture
def deck(rng: Random) -> InMemoryCardStore:
    return InMemoryCardStore(make_black_cards(), make_white_cards(), rng=rng)


@pytest.fixture
def notifier() -> RecordingNotifier:
    return RecordingNotifier()


@pytest.fixture
def service(
    games: InMemoryGameRepository,
    deck: InMemoryCardStore,
    notifier: RecordingNotifier,
    rng: Random,
) -> GameService:
    return GameService(games, deck, notifier, rng=rng)
