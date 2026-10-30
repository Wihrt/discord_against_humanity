"""Valkey-backed card store, implementing both :class:`CardDeck` and :class:`CardCatalog`.

Key layout (compatible with catalogs seeded by earlier versions)::

    black_cards:ids        SET of card IDs
    black_cards:<id>       JSON {"text": str, "pick": int}
    white_cards:ids        SET of card IDs
    white_cards:<id>       JSON {"text": str}
"""

import json
import logging
from collections.abc import Awaitable, Collection, Sequence
from itertools import batched
from typing import Any

from valkey.asyncio import Valkey

from discord_against_humanity.domain.cards import BlackCard, WhiteCard
from discord_against_humanity.domain.errors import DeckExhaustedError

logger = logging.getLogger(__name__)

_BLACK = "black_cards"
_WHITE = "white_cards"
_BATCH_SIZE = 1000


async def _result[T](value: Awaitable[T] | T) -> T:
    # valkey-py types its commands for both its sync and async clients.
    return await value if isinstance(value, Awaitable) else value


class ValkeyCardStore:
    def __init__(self, client: Valkey) -> None:
        self._client = client

    # CardDeck
    # -------------------------------------------------------------------------

    async def draw_black_card(self, exclude: Collection[str]) -> BlackCard:
        ((card_id, data),) = await self._draw(_BLACK, 1, exclude)
        return BlackCard(id=card_id, text=data["text"], pick=int(data.get("pick", 1)))

    async def draw_white_cards(self, count: int, exclude: Collection[str]) -> list[WhiteCard]:
        if count <= 0:
            return []
        drawn = await self._draw(_WHITE, count, exclude)
        return [WhiteCard(id=card_id, text=data["text"]) for card_id, data in drawn]

    async def _draw(
        self, collection: str, count: int, exclude: Collection[str]
    ) -> list[tuple[str, dict[str, Any]]]:
        excluded = set(exclude)
        ids_key = f"{collection}:ids"
        total = await _result(self._client.scard(ids_key))
        # Sampling ``count + len(excluded)`` distinct members guarantees at
        # least ``count`` non-excluded ones whenever enough cards exist.
        sample_size = min(total, count + len(excluded))
        if sample_size < count:
            raise DeckExhaustedError
        sample = await _result(self._client.srandmember(ids_key, sample_size))
        chosen = [card_id for card_id in sample if card_id not in excluded][:count]
        if len(chosen) < count:
            raise DeckExhaustedError
        raw = await self._client.mget([f"{collection}:{card_id}" for card_id in chosen])
        drawn = [
            (card_id, json.loads(value))
            for card_id, value in zip(chosen, raw, strict=True)
            if value is not None
        ]
        if len(drawn) < count:
            logger.warning("Some %s IDs have no card document", collection)
            raise DeckExhaustedError
        return drawn

    # CardCatalog
    # -------------------------------------------------------------------------

    async def count(self) -> tuple[int, int]:
        return (
            await _result(self._client.scard(f"{_BLACK}:ids")),
            await _result(self._client.scard(f"{_WHITE}:ids")),
        )

    async def add(self, black: Sequence[BlackCard], white: Sequence[WhiteCard]) -> None:
        black_docs = [(c.id, {"text": c.text, "pick": c.pick}) for c in black]
        white_docs = [(c.id, {"text": c.text}) for c in white]
        await self._write(_BLACK, black_docs)
        await self._write(_WHITE, white_docs)

    async def _write(self, collection: str, docs: Sequence[tuple[str, dict[str, Any]]]) -> None:
        for chunk in batched(docs, _BATCH_SIZE, strict=False):
            async with self._client.pipeline(transaction=False) as pipe:
                pipe.mset({f"{collection}:{cid}": json.dumps(doc) for cid, doc in chunk})
                pipe.sadd(f"{collection}:ids", *(cid for cid, _ in chunk))
                await pipe.execute()

    async def clear(self) -> None:
        for collection in (_BLACK, _WHITE):
            ids_key = f"{collection}:ids"
            ids = list(await _result(self._client.smembers(ids_key)))
            for chunk in batched(ids, _BATCH_SIZE, strict=False):
                await self._client.delete(*(f"{collection}:{cid}" for cid in chunk))
            await self._client.delete(ids_key)
