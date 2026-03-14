"""MongoDB document base class."""

import logging
from abc import abstractmethod
from typing import Any, Self

from bson.objectid import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from discord_against_humanity.utils.debug import async_log_event

logger = logging.getLogger(__name__)


class MongoDocument:
    """Abstract base class for MongoDB documents."""

    _DATABASE: str | None = None
    _COLLECTION: str | None = None

    def __init__(self, mongo_client: AsyncIOMotorClient) -> None:  # type: ignore[type-arg]
        """Create a new MongoDocument instance.

        Args:
            mongo_client: Motor client connected to the database.
        """
        self._client = mongo_client
        self._collection = self._client[self._DATABASE][self._COLLECTION]
        self._document: dict[str, Any] = {}

    @property
    def document_id(self) -> ObjectId | None:
        """Get the MongoDB document ID.

        Returns:
            The ObjectId of this document, or None.
        """
        try:
            return self._document["_id"]
        except KeyError:
            return None

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
            document_id: Optional ObjectId to load. Uses current ID if not provided.
        """
        search = {"_id": self.document_id}
        if document_id:
            search = {"_id": document_id}
        self._document = await self._collection.find_one(search)

    @async_log_event
    async def save(self) -> None:
        """Save the document to MongoDB (insert or replace)."""
        if not self.document_id:
            result = await self._collection.insert_one(self._document)
            self.document_id = result.inserted_id
        else:
            self._document = await self._collection.find_one_and_replace(
                {"_id": self.document_id}, self._document
            )
        await self.get(self.document_id)

    @async_log_event
    async def delete(self) -> None:
        """Delete the document from MongoDB."""
        if self.document_id:
            await self._collection.delete_one({"_id": self.document_id})

    @classmethod
    @abstractmethod
    async def create(cls) -> Self:
        """Create a new instance of this document type."""
        raise NotImplementedError("Not implemented")
