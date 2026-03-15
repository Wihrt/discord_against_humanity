"""Abstract repository port — defines the persistence contract."""

from abc import ABC, abstractmethod
from typing import Any


class DocumentNotFoundError(Exception):
    """Raised when a document is not found in the store."""


class Repository(ABC):
    """Abstract base class for repositories (Repository pattern).

    This is a *port* in the hexagonal architecture: it defines the
    contract that any persistence adapter must satisfy.
    """

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
