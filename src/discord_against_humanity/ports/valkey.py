"""Valkey adapter — concrete persistence backed by Valkey."""

import json
import logging
from typing import Any
from uuid import uuid4

import valkey.asyncio as valkey

from discord_against_humanity.ports.repository import (
    DocumentNotFoundError,
    Repository,
    RepositoryFactory,
)

logger = logging.getLogger(__name__)

# Secondary-index configuration per collection.
# Maps collection names to the field names that should be indexed for
# ``find_one`` look-ups.  Add an entry here when a domain model needs
# to query by a field other than its primary ID.
_INDEX_FIELDS: dict[str, list[str]] = {
    "games": ["guild"],
    "players": ["user"],
}


class ValkeyRepository(Repository):
    """Concrete Valkey repository backed by valkey-py."""

    def __init__(
        self,
        client: valkey.Valkey,
        collection: str,
        index_fields: list[str] | None = None,
    ) -> None:
        """Initialize the repository.

        Args:
            client: Async Valkey client.
            collection: Collection name used as key prefix.
            index_fields: Fields to create secondary indices for
                (used by ``find_one``).
        """
        self._client = client
        self._collection = collection
        self._index_fields = index_fields or []

    def _doc_key(self, doc_id: str) -> str:
        """Build the Valkey key for a document."""
        return f"{self._collection}:{doc_id}"

    def _ids_key(self) -> str:
        """Build the Valkey key for the ID set."""
        return f"{self._collection}:ids"

    def _index_key(self, field: str, value: Any) -> str:
        """Build the Valkey key for a secondary index."""
        return f"{self._collection}:idx:{field}:{value}"

    async def find_by_id(
        self, document_id: str
    ) -> dict[str, Any] | None:
        """Find a document by its ID."""
        data = await self._client.get(self._doc_key(document_id))
        if data is None:
            return None
        doc: dict[str, Any] = json.loads(data)
        doc["_id"] = document_id
        return doc

    async def find_one(
        self, query: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Find a single document matching a query via secondary indices."""
        for field, value in query.items():
            if field in self._index_fields:
                doc_id = await self._client.get(
                    self._index_key(field, value)
                )
                if doc_id is not None:
                    if isinstance(doc_id, bytes):
                        doc_id = doc_id.decode()
                    return await self.find_by_id(doc_id)
        return None

    async def insert(self, document: dict[str, Any]) -> str:
        """Insert a new document and return its ID."""
        doc_id = str(document.pop("_id", None) or uuid4())
        await self._client.set(
            self._doc_key(doc_id), json.dumps(document)
        )
        await self._client.sadd(self._ids_key(), doc_id)  # type: ignore[misc]
        for field in self._index_fields:
            if field in document:
                await self._client.set(
                    self._index_key(field, document[field]),
                    doc_id,
                )
        return doc_id

    async def replace(
        self, document_id: str, document: dict[str, Any]
    ) -> dict[str, Any]:
        """Replace an existing document.

        Raises:
            DocumentNotFoundError: If no document matches the ID.
        """
        if not await self._client.exists(
            self._doc_key(document_id)
        ):
            raise DocumentNotFoundError(
                f"Document {document_id} not found for replacement"
            )
        doc = {k: v for k, v in document.items() if k != "_id"}
        await self._client.set(
            self._doc_key(document_id), json.dumps(doc)
        )
        for field in self._index_fields:
            if field in doc:
                await self._client.set(
                    self._index_key(field, doc[field]),
                    document_id,
                )
        result = dict(doc)
        result["_id"] = document_id
        return result

    async def delete_by_id(self, document_id: str) -> None:
        """Delete a document by its ID."""
        data = await self._client.get(self._doc_key(document_id))
        if data is not None:
            doc = json.loads(data)
            for field in self._index_fields:
                if field in doc:
                    await self._client.delete(
                        self._index_key(field, doc[field])
                    )
        await self._client.delete(self._doc_key(document_id))
        await self._client.srem(self._ids_key(), document_id)  # type: ignore[misc]

    async def random_member(self) -> dict[str, Any] | None:
        """Get a random document from the collection."""
        doc_id = await self._client.srandmember(self._ids_key())  # type: ignore[misc]
        if doc_id is None:
            return None
        if isinstance(doc_id, bytes):
            doc_id = doc_id.decode()
        return await self.find_by_id(doc_id)

    async def count(self) -> int:
        """Count the number of documents in the collection."""
        result = await self._client.scard(self._ids_key())  # type: ignore[misc]
        return int(result)


def create_repo_factory(client: valkey.Valkey) -> RepositoryFactory:
    """Build a :class:`RepositoryFactory` backed by a Valkey client.

    The returned callable creates :class:`ValkeyRepository` instances for
    any collection name, automatically wiring secondary-index fields
    from the module-level ``_INDEX_FIELDS`` mapping.

    Args:
        client: An async Valkey client.

    Returns:
        A factory callable ``(collection: str) -> Repository``.
    """

    def factory(collection: str) -> Repository:
        return ValkeyRepository(
            client, collection, _INDEX_FIELDS.get(collection)
        )

    return factory
