"""MongoDB document base class and repository interfaces."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Self

from bson.objectid import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from discord_against_humanity.utils.debug import async_log_event

logger = logging.getLogger(__name__)


class DocumentNotFoundError(Exception):
    """Raised when a document is not found in MongoDB."""


class Repository(ABC):
    """Abstract base class for repositories (Repository pattern)."""

    @abstractmethod
    async def find_by_id(
        self, document_id: ObjectId
    ) -> dict[str, Any] | None:
        """Find a document by its ID.

        Args:
            document_id: The ObjectId to look up.

        Returns:
            The document dict, or None if not found.
        """

    @abstractmethod
    async def find_one(
        self, query: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Find a single document matching a query.

        Args:
            query: MongoDB query filter.

        Returns:
            The matching document dict, or None.
        """

    @abstractmethod
    async def insert(self, document: dict[str, Any]) -> ObjectId:
        """Insert a new document.

        Args:
            document: The document to insert.

        Returns:
            The inserted document's ObjectId.
        """

    @abstractmethod
    async def replace(
        self, document_id: ObjectId, document: dict[str, Any]
    ) -> dict[str, Any]:
        """Replace an existing document.

        Args:
            document_id: The ObjectId of the document to replace.
            document: The replacement document.

        Returns:
            The replaced document.

        Raises:
            DocumentNotFoundError: If no document matches the ID.
        """

    @abstractmethod
    async def delete_by_id(self, document_id: ObjectId) -> None:
        """Delete a document by its ID.

        Args:
            document_id: The ObjectId of the document to delete.
        """

    @abstractmethod
    async def aggregate(
        self, pipeline: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Run an aggregation pipeline.

        Args:
            pipeline: MongoDB aggregation pipeline stages.

        Returns:
            List of result documents.
        """


class MongoRepository(Repository):
    """Concrete MongoDB repository backed by Motor."""

    def __init__(
        self,
        client: AsyncIOMotorClient,  # type: ignore[type-arg]
        database: str,
        collection: str,
    ) -> None:
        """Initialize the repository.

        Args:
            client: Motor async MongoDB client.
            database: Database name.
            collection: Collection name.
        """
        self._client = client
        self._collection = client[database][collection]

    async def find_by_id(
        self, document_id: ObjectId
    ) -> dict[str, Any] | None:
        """Find a document by its ID."""
        return await self._collection.find_one({"_id": document_id})

    async def find_one(
        self, query: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Find a single document matching a query."""
        return await self._collection.find_one(query)

    async def insert(self, document: dict[str, Any]) -> ObjectId:
        """Insert a new document and return its ID."""
        result = await self._collection.insert_one(document)
        return result.inserted_id

    async def replace(
        self, document_id: ObjectId, document: dict[str, Any]
    ) -> dict[str, Any]:
        """Replace an existing document.

        Raises:
            DocumentNotFoundError: If no document matches the ID.
        """
        from pymongo import ReturnDocument

        result = await self._collection.find_one_and_replace(
            {"_id": document_id},
            document,
            return_document=ReturnDocument.AFTER,
        )
        if result is None:
            raise DocumentNotFoundError(
                f"Document {document_id} not found for replacement"
            )
        return result

    async def delete_by_id(self, document_id: ObjectId) -> None:
        """Delete a document by its ID."""
        await self._collection.delete_one({"_id": document_id})

    async def aggregate(
        self, pipeline: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Run an aggregation pipeline."""
        results: list[dict[str, Any]] = []
        async for doc in self._collection.aggregate(pipeline):
            results.append(doc)
        return results


class MongoDocument:
    """Abstract base class for MongoDB documents.

    Subclasses must set ``_DATABASE`` and ``_COLLECTION`` to non-None
    strings.  The class delegates all I/O to a :class:`Repository`
    instance so that storage can be swapped or mocked.
    """

    _DATABASE: str = ""
    _COLLECTION: str = ""

    def __init__(
        self,
        mongo_client: AsyncIOMotorClient,  # type: ignore[type-arg]
        *,
        repository: Repository | None = None,
    ) -> None:
        """Create a new MongoDocument instance.

        Args:
            mongo_client: Motor client connected to the database.
            repository: Optional repository override (for testing).

        Raises:
            ValueError: If _DATABASE or _COLLECTION are not set.
        """
        if not self._DATABASE or not self._COLLECTION:
            raise ValueError(
                f"{type(self).__name__} must define "
                f"_DATABASE and _COLLECTION"
            )
        self._client = mongo_client
        self._repo = repository or MongoRepository(
            mongo_client, self._DATABASE, self._COLLECTION
        )
        self._document: dict[str, Any] = {}

    @property
    def document_id(self) -> ObjectId | None:
        """Get the MongoDB document ID.

        Returns:
            The ObjectId of this document, or None.
        """
        return self._document.get("_id")

    @document_id.setter
    def document_id(self, value: ObjectId) -> None:
        """Set the MongoDB document ID.

        Args:
            value: The ObjectId to assign.

        Raises:
            TypeError: If value is not an ObjectId.
        """
        if not isinstance(value, ObjectId):
            raise TypeError("document_id must be an ObjectId")
        self._document["_id"] = value

    @async_log_event
    async def get(self, document_id: ObjectId | None = None) -> None:
        """Load the document from MongoDB.

        Args:
            document_id: Optional ObjectId to load.
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
        """Save the document to MongoDB (insert or replace)."""
        if not self.document_id:
            inserted_id = await self._repo.insert(self._document)
            self.document_id = inserted_id
        else:
            self._document = await self._repo.replace(
                self.document_id, self._document
            )

    @async_log_event
    async def delete(self) -> None:
        """Delete the document from MongoDB."""
        if self.document_id:
            await self._repo.delete_by_id(self.document_id)

    @classmethod
    @abstractmethod
    async def create(cls) -> Self:
        """Create a new instance of this document type."""
        raise NotImplementedError("Not implemented")
