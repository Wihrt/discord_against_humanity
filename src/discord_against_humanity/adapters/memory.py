"""In-memory adapters, for tests and for trying the bot without Valkey."""

from collections.abc import Collection, Sequence
from copy import deepcopy
from random import Random

from discord_against_humanity.domain.cards import BlackCard, WhiteCard
from discord_against_humanity.domain.errors import DeckExhaustedError
from discord_against_humanity.domain.game import Game


class InMemoryGameRepository:
    def __init__(self) -> None:
        self.games: dict[int, Game] = {}

    async def get(self, guild_id: int) -> Game | None:
        # Copies mimic a real store: callers never share live state.
        game = self.games.get(guild_id)
        return deepcopy(game) if game is not None else None

    async def save(self, game: Game) -> None:
        self.games[game.guild_id] = deepcopy(game)

    async def delete(self, guild_id: int) -> None:
        self.games.pop(guild_id, None)


class InMemoryCardStore:
    def __init__(
        self,
        black: Sequence[BlackCard] = (),
        white: Sequence[WhiteCard] = (),
        rng: Random | None = None,
    ) -> None:
        self.black = {card.id: card for card in black}
        self.white = {card.id: card for card in white}
        self._rng = rng or Random()

    async def draw_black_card(self, exclude: Collection[str]) -> BlackCard:
        available = [c for cid, c in self.black.items() if cid not in exclude]
        if not available:
            raise DeckExhaustedError
        return self._rng.choice(available)

    async def draw_white_cards(self, count: int, exclude: Collection[str]) -> list[WhiteCard]:
        available = [c for cid, c in self.white.items() if cid not in exclude]
        if len(available) < count:
            raise DeckExhaustedError
        return self._rng.sample(available, count)

    async def count(self) -> tuple[int, int]:
        return len(self.black), len(self.white)

    async def add(self, black: Sequence[BlackCard], white: Sequence[WhiteCard]) -> None:
        self.black.update((card.id, card) for card in black)
        self.white.update((card.id, card) for card in white)

    async def clear(self) -> None:
        self.black.clear()
        self.white.clear()
