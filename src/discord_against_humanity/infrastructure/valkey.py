"""Valkey document base class and repository interfaces."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Self
from uuid import uuid4

import valkey.asyncio as valkey

from discord_against_humanity.utils.debug import async_log_event

logger = logging.getLogger(__name__)


class DocumentNotFoundError(Exception):
    """Raised when a document is not found in Valkey."""


class Repository(ABC):
    """Abstract base class for repositories (Repository pattern)."""

    @abstractmethod
    async def find_by_id(
        self, document_id: str
    ) -> dict[str, Any] | None:
        """Find a document by its ID.

        Args:
            document_id: The document ID to look up.

        Returns:
            The document dict, or None if not found.
        """

    @abstractmethod
    async def find_one(
        self, query: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Find a single document matching a query.

        Args:
            query: Query filter (field-value pairs matched via indices).

        Returns:
            The matching document dict, or None.
        """

    @abstractmethod
    async def insert(self, document: dict[str, Any]) -> str:
        """Insert a new document.

        Args:
            document: The document to insert.

        Returns:
            The inserted document's ID.
        """

    @abstractmethod
    async def replace(
        self, document_id: str, document: dict[str, Any]
    ) -> dict[str, Any]:
        """Replace an existing document.

        Args:
            document_id: The ID of the document to replace.
            document: The replacement document.

        Returns:
            The replaced document.

        Raises:
            DocumentNotFoundError: If no document matches the ID.
        """

    @abstractmethod
    async def delete_by_id(self, document_id: str) -> None:
        """Delete a document by its ID.

        Args:
            document_id: The ID of the document to delete.
        """

    @abstractmethod
    async def random_member(self) -> dict[str, Any] | None:
        """Get a random document from the collection.

        Returns:
            A randomly selected document, or None if empty.
        """

    @abstractmethod
    async def count(self) -> int:
        """Count the number of documents in the collection.

        Returns:
            The total number of documents.
        """


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
        await self._client.sadd(self._ids_key(), doc_id)
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
        await self._client.srem(self._ids_key(), document_id)

    async def random_member(self) -> dict[str, Any] | None:
        """Get a random document from the collection."""
        doc_id = await self._client.srandmember(self._ids_key())
        if doc_id is None:
            return None
        if isinstance(doc_id, bytes):
            doc_id = doc_id.decode()
        return await self.find_by_id(doc_id)

    async def count(self) -> int:
        """Count the number of documents in the collection."""
        result = await self._client.scard(self._ids_key())
        return int(result)


class ValkeyDocument:
    """Abstract base class for Valkey documents.

    Subclasses must set ``_COLLECTION`` to a non-empty string.
    The class delegates all I/O to a :class:`Repository` instance
    so that storage can be swapped or mocked.
    """

    _COLLECTION: str = ""

    def __init__(
        self,
        valkey_client: valkey.Valkey,
        *,
        repository: Repository | None = None,
    ) -> None:
        """Create a new ValkeyDocument instance.

        Args:
            valkey_client: Async Valkey client.
            repository: Optional repository override (for testing).

        Raises:
            ValueError: If _COLLECTION is not set.
        """
        if not self._COLLECTION:
            raise ValueError(
                f"{type(self).__name__} must define _COLLECTION"
            )
        self._client = valkey_client
        self._repo = repository or ValkeyRepository(
            valkey_client, self._COLLECTION
        )
        self._document: dict[str, Any] = {}

    @property
    def document_id(self) -> str | None:
        """Get the document ID.

        Returns:
            The ID of this document, or None.
        """
        return self._document.get("_id")

    @document_id.setter
    def document_id(self, value: str) -> None:
        """Set the document ID.

        Args:
            value: The ID to assign.

        Raises:
            TypeError: If value is not a str.
        """
        if not isinstance(value, str):
            raise TypeError("document_id must be a str")
        self._document["_id"] = value

    @async_log_event
    async def get(self, document_id: str | None = None) -> None:
        """Load the document from Valkey.

        Args:
            document_id: Optional ID to load.
                Uses current ID if not provided.
        """
        target_id = document_id or self.document_id
        if target_id is None:
            return
        result = await self._repo.find_by_id(target_id)
        if result is not None:
            self._document = result

    @async_log_event
    async def save(self) -> None:
        """Save the document to Valkey (insert or replace)."""
        if not self.document_id:
            inserted_id = await self._repo.insert(self._document)
            self.document_id = inserted_id
        else:
            self._document = await self._repo.replace(
                self.document_id, self._document
            )

    @async_log_event
    async def delete(self) -> None:
        """Delete the document from Valkey."""
        if self.document_id:
            await self._repo.delete_by_id(self.document_id)

    @classmethod
    @abstractmethod
    async def create(cls) -> Self:
        """Create a new instance of this document type."""
        raise NotImplementedError("Not implemented")
