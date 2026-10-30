"""Ports: the interfaces the application needs from the outside world.

Driven adapters (storage, chat platform) implement these protocols; the
application layer only ever depends on them, never on a concrete adapter.
"""

from collections.abc import Collection, Sequence
from typing import Protocol

from discord_against_humanity.domain.cards import BlackCard, WhiteCard
from discord_against_humanity.domain.game import Game, RoundResult


class GameRepository(Protocol):
    """Persists one game per guild."""

    async def get(self, guild_id: int) -> Game | None: ...

    async def save(self, game: Game) -> None: ...

    async def delete(self, guild_id: int) -> None: ...


class CardDeck(Protocol):
    """Draws random cards from the card catalog."""

    async def draw_black_card(self, exclude: Collection[str]) -> BlackCard:
        """Raise ``DeckExhaustedError`` when every card is excluded."""
        ...

    async def draw_white_cards(self, count: int, exclude: Collection[str]) -> list[WhiteCard]:
        """Raise ``DeckExhaustedError`` when fewer than *count* cards remain."""
        ...


class CardCatalog(Protocol):
    """Writable side of the card store, used to seed it."""

    async def count(self) -> tuple[int, int]:
        """Return the number of ``(black, white)`` cards stored."""
        ...

    async def add(self, black: Sequence[BlackCard], white: Sequence[WhiteCard]) -> None: ...

    async def clear(self) -> None: ...


class GameNotifier(Protocol):
    """Tells players what happens in their game."""

    async def player_joined(self, game: Game, user_id: int) -> None: ...

    async def player_left(self, game: Game, user_id: int) -> None: ...

    async def game_started(self, game: Game) -> None: ...

    async def round_started(self, game: Game) -> None: ...

    async def answer_received(self, game: Game, user_id: int) -> None: ...

    async def judging_started(self, game: Game) -> None: ...

    async def round_cancelled(self, game: Game, reason: str) -> None: ...

    async def round_won(self, game: Game, result: RoundResult) -> None: ...

    async def game_over(self, game: Game, winner_id: int) -> None: ...

    async def game_stopped(self, game: Game, reason: str) -> None: ...
