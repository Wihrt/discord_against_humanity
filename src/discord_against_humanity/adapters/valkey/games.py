"""Valkey-backed :class:`GameRepository`."""

import json

from valkey.asyncio import Valkey

from discord_against_humanity.adapters.valkey.serialization import (
    game_from_dict,
    game_to_dict,
)
from discord_against_humanity.domain.game import Game


class ValkeyGameRepository:
    """Stores each game as a single JSON document keyed by guild."""

    def __init__(self, client: Valkey, prefix: str = "cah:game") -> None:
        self._client = client
        self._prefix = prefix

    def _key(self, guild_id: int) -> str:
        return f"{self._prefix}:{guild_id}"

    async def get(self, guild_id: int) -> Game | None:
        raw = await self._client.get(self._key(guild_id))
        if raw is None:
            return None
        return game_from_dict(json.loads(raw))

    async def save(self, game: Game) -> None:
        await self._client.set(self._key(game.guild_id), json.dumps(game_to_dict(game)))

    async def delete(self, guild_id: int) -> None:
        await self._client.delete(self._key(guild_id))
