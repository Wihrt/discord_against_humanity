"""Document base class — domain object with persistence support."""

import logging
from abc import abstractmethod
from typing import Any, Self

import valkey.asyncio as valkey

from discord_against_humanity.adapters.valkey import ValkeyRepository
from discord_against_humanity.ports.repository import Repository
from discord_against_humanity.utils.debug import async_log_event

logger = logging.getLogger(__name__)


class Document:
    """Abstract base class for persistable domain documents.

    Subclasses must set ``_COLLECTION`` to a non-empty string.
    The class delegates all I/O to a :class:`Repository` instance
    so that the storage adapter can be swapped or mocked.
    """

    _COLLECTION: str = ""

    def __init__(
        self,
        valkey_client: valkey.Valkey,
        *,
        repository: Repository | None = None,
    ) -> None:
        """Create a new Document instance.

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
        """Load the document from the store.

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
        """Save the document to the store (insert or replace)."""
        if not self.document_id:
            inserted_id = await self._repo.insert(self._document)
            self.document_id = inserted_id
        else:
            self._document = await self._repo.replace(
                self.document_id, self._document
            )

    @async_log_event
    async def delete(self) -> None:
        """Delete the document from the store."""
        if self.document_id:
            await self._repo.delete_by_id(self.document_id)

    @classmethod
    @abstractmethod
    async def create(cls) -> Self:
        """Create a new instance of this document type."""
        raise NotImplementedError("Not implemented")
