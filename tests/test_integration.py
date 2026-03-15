"""Integration tests using Testcontainers with a real MongoDB instance.

These tests verify that the repository pattern and domain models work
correctly against an actual MongoDB server.  They are automatically
skipped when Docker is not available.
"""

import asyncio

import pytest
from bson.objectid import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from discord_against_humanity.infrastructure.mongo import (
    DocumentNotFoundError,
    MongoRepository,
)

# ---------------------------------------------------------------------------
# Testcontainers fixture
# ---------------------------------------------------------------------------

_can_use_docker = True
try:
    from testcontainers.mongodb import MongoDbContainer  # type: ignore[import-untyped]
except ImportError:
    _can_use_docker = False

pytestmark = pytest.mark.skipif(
    not _can_use_docker,
    reason="testcontainers[mongodb] not installed",
)


@pytest.fixture(scope="module")
def mongo_container():
    """Start a MongoDB container for the duration of the test module."""
    with MongoDbContainer("mongo:8") as container:
        yield container


@pytest.fixture
def motor_client(mongo_container):  # type: ignore[no-untyped-def]
    """Create an async Motor client connected to the test container."""
    connection_url = mongo_container.get_connection_url()
    client: AsyncIOMotorClient = AsyncIOMotorClient(connection_url)  # type: ignore[type-arg]
    yield client
    client.close()


@pytest.fixture
def repository(motor_client):  # type: ignore[no-untyped-def]
    """Create a MongoRepository using the test container."""
    return MongoRepository(
        motor_client, "test_db", "test_collection"
    )


# ---------------------------------------------------------------------------
# Repository integration tests
# ---------------------------------------------------------------------------


class TestMongoRepositoryIntegration:
    """Integration tests for MongoRepository with a real MongoDB."""

    async def test_insert_and_find_by_id(self, repository):
        """Insert a document and retrieve it by ObjectId."""
        doc = {"name": "test_card", "text": "Hello world"}
        inserted_id = await repository.insert(doc)

        assert isinstance(inserted_id, ObjectId)
        result = await repository.find_by_id(inserted_id)
        assert result is not None
        assert result["name"] == "test_card"
        assert result["text"] == "Hello world"

    async def test_find_one(self, repository):
        """Find a document by query."""
        doc = {"guild": 42, "playing": True}
        await repository.insert(doc)

        result = await repository.find_one({"guild": 42})
        assert result is not None
        assert result["guild"] == 42
        assert result["playing"] is True

    async def test_find_one_returns_none_when_missing(self, repository):
        """find_one returns None when no document matches."""
        result = await repository.find_one(
            {"nonexistent": "value"}
        )
        assert result is None

    async def test_find_by_id_returns_none_when_missing(
        self, repository
    ):
        """find_by_id returns None for a nonexistent ObjectId."""
        result = await repository.find_by_id(ObjectId())
        assert result is None

    async def test_replace(self, repository):
        """Replace an existing document."""
        doc = {"value": "original"}
        inserted_id = await repository.insert(doc)

        updated = await repository.replace(
            inserted_id, {"value": "updated"}
        )
        assert updated["value"] == "updated"

        reloaded = await repository.find_by_id(inserted_id)
        assert reloaded is not None
        assert reloaded["value"] == "updated"

    async def test_replace_nonexistent_raises_error(self, repository):
        """Replace raises DocumentNotFoundError for missing docs."""
        with pytest.raises(DocumentNotFoundError):
            await repository.replace(ObjectId(), {"value": "nope"})

    async def test_delete_by_id(self, repository):
        """Delete a document and confirm it's gone."""
        doc = {"to_delete": True}
        inserted_id = await repository.insert(doc)

        await repository.delete_by_id(inserted_id)
        result = await repository.find_by_id(inserted_id)
        assert result is None

    async def test_aggregate(self, repository):
        """Run a simple aggregation pipeline."""
        await repository.insert({"category": "a", "score": 10})
        await repository.insert({"category": "a", "score": 20})
        await repository.insert({"category": "b", "score": 5})

        pipeline = [
            {"$match": {"category": "a"}},
            {
                "$group": {
                    "_id": "$category",
                    "total": {"$sum": "$score"},
                }
            },
        ]
        results = await repository.aggregate(pipeline)
        assert len(results) == 1
        assert results[0]["_id"] == "a"
        assert results[0]["total"] == 30


# ---------------------------------------------------------------------------
# MongoDocument integration tests
# ---------------------------------------------------------------------------


class TestMongoDocumentIntegration:
    """Integration tests for MongoDocument save/get/delete cycle."""

    async def test_save_get_delete_cycle(self, motor_client):
        """Full lifecycle: save, get, and delete a document."""
        from discord_against_humanity.infrastructure.mongo import (
            MongoDocument,
        )

        class TestDoc(MongoDocument):
            _DATABASE = "test_db"
            _COLLECTION = "lifecycle_test"

            @classmethod
            async def create(cls):  # type: ignore[override]
                raise NotImplementedError

        doc = TestDoc(motor_client)
        doc._document = {"field": "value"}

        # Save (insert)
        await doc.save()
        assert doc.document_id is not None

        # Get (reload)
        original_id = doc.document_id
        doc._document = {}
        await doc.get(original_id)
        assert doc._document["field"] == "value"

        # Save (update)
        doc._document["field"] = "updated"
        await doc.save()
        await doc.get(original_id)
        assert doc._document["field"] == "updated"

        # Delete
        await doc.delete()
        doc._document = {}
        await doc.get(original_id)
        assert doc.document_id is None

    async def test_concurrent_saves_do_not_corrupt(
        self, motor_client
    ):
        """Concurrent saves to different documents don't interfere."""
        from discord_against_humanity.infrastructure.mongo import (
            MongoDocument,
        )

        class TestDoc(MongoDocument):
            _DATABASE = "test_db"
            _COLLECTION = "concurrent_test"

            @classmethod
            async def create(cls):  # type: ignore[override]
                raise NotImplementedError

        doc_a = TestDoc(motor_client)
        doc_a._document = {"name": "A"}
        doc_b = TestDoc(motor_client)
        doc_b._document = {"name": "B"}

        await asyncio.gather(doc_a.save(), doc_b.save())

        assert doc_a.document_id is not None
        assert doc_b.document_id is not None
        assert doc_a.document_id != doc_b.document_id

        # Verify each document has correct data
        await doc_a.get(doc_a.document_id)
        await doc_b.get(doc_b.document_id)
        assert doc_a._document["name"] == "A"
        assert doc_b._document["name"] == "B"
