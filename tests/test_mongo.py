"""Tests for the MongoDocument base class and Repository pattern."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from bson.objectid import ObjectId

from discord_against_humanity.infrastructure.mongo import (
    DocumentNotFoundError,
    MongoDocument,
    MongoRepository,
    Repository,
)


class ConcreteDocument(MongoDocument):
    """Concrete subclass for testing the abstract MongoDocument."""

    _DATABASE = "test_db"
    _COLLECTION = "test_collection"

    @classmethod
    async def create(cls):
        raise NotImplementedError


@pytest.fixture
def mock_repo():
    """Create a mock Repository."""
    repo = MagicMock(spec=Repository)
    repo.find_by_id = AsyncMock(return_value=None)
    repo.find_one = AsyncMock(return_value=None)
    repo.insert = AsyncMock(return_value=ObjectId())
    repo.replace = AsyncMock(return_value={})
    repo.delete_by_id = AsyncMock()
    repo.aggregate = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def doc(mock_mongo_client, mock_repo):
    """Create a ConcreteDocument with a mock repo."""
    return ConcreteDocument(mock_mongo_client, repository=mock_repo)


class TestDocumentId:
    """Tests for document_id property."""

    def test_document_id_none_when_empty(self, doc):
        assert doc.document_id is None

    def test_document_id_getter(self, doc):
        oid = ObjectId()
        doc._document["_id"] = oid
        assert doc.document_id == oid

    def test_document_id_setter(self, doc):
        oid = ObjectId()
        doc.document_id = oid
        assert doc._document["_id"] == oid

    def test_document_id_setter_rejects_non_objectid(self, doc):
        with pytest.raises(
            TypeError, match="document_id must be an ObjectId"
        ):
            doc.document_id = "not-an-objectid"

    def test_document_id_setter_rejects_int(self, doc):
        with pytest.raises(TypeError):
            doc.document_id = 12345


class TestInit:
    """Tests for __init__ and class attributes."""

    def test_database_and_collection(self):
        assert ConcreteDocument._DATABASE == "test_db"
        assert ConcreteDocument._COLLECTION == "test_collection"

    def test_client_stored(self, doc, mock_mongo_client):
        assert doc._client is mock_mongo_client

    def test_empty_document(self, doc):
        assert doc._document == {}

    def test_raises_if_database_not_set(self, mock_mongo_client):
        class BadDoc(MongoDocument):
            _DATABASE = ""
            _COLLECTION = "col"

            @classmethod
            async def create(cls):
                raise NotImplementedError

        with pytest.raises(ValueError, match="must define"):
            BadDoc(mock_mongo_client)

    def test_raises_if_collection_not_set(self, mock_mongo_client):
        class BadDoc(MongoDocument):
            _DATABASE = "db"
            _COLLECTION = ""

            @classmethod
            async def create(cls):
                raise NotImplementedError

        with pytest.raises(ValueError, match="must define"):
            BadDoc(mock_mongo_client)

    def test_custom_repository_used(self, mock_mongo_client, mock_repo):
        doc = ConcreteDocument(
            mock_mongo_client, repository=mock_repo
        )
        assert doc._repo is mock_repo


class TestGet:
    """Tests for the get() method."""

    async def test_get_does_nothing_when_no_id(self, doc, mock_repo):
        await doc.get()
        mock_repo.find_by_id.assert_not_awaited()

    async def test_get_uses_current_id(self, doc, mock_repo):
        oid = ObjectId()
        doc._document["_id"] = oid
        mock_repo.find_by_id = AsyncMock(
            return_value={"_id": oid, "data": "value"}
        )
        await doc.get()
        mock_repo.find_by_id.assert_awaited_once_with(oid)
        assert doc._document["data"] == "value"

    async def test_get_with_explicit_id(self, doc, mock_repo):
        other_id = ObjectId()
        mock_repo.find_by_id = AsyncMock(
            return_value={"_id": other_id, "key": "val"}
        )
        await doc.get(other_id)
        mock_repo.find_by_id.assert_awaited_once_with(other_id)
        assert doc._document["key"] == "val"

    async def test_get_leaves_document_unchanged_on_not_found(
        self, doc, mock_repo
    ):
        oid = ObjectId()
        doc._document = {"_id": oid, "existing": "data"}
        mock_repo.find_by_id = AsyncMock(return_value=None)
        await doc.get(oid)
        assert doc._document["existing"] == "data"


class TestSave:
    """Tests for the save() method."""

    async def test_save_insert_new_document(self, doc, mock_repo):
        new_id = ObjectId()
        mock_repo.insert = AsyncMock(return_value=new_id)
        await doc.save()
        mock_repo.insert.assert_awaited_once()
        assert doc.document_id == new_id

    async def test_save_replaces_existing_document(
        self, doc, mock_repo
    ):
        oid = ObjectId()
        doc.document_id = oid
        doc._document["field"] = "updated"
        replaced = {"_id": oid, "field": "updated"}
        mock_repo.replace = AsyncMock(return_value=replaced)
        await doc.save()
        mock_repo.replace.assert_awaited_once_with(
            oid, doc._document
        )


class TestDelete:
    """Tests for the delete() method."""

    async def test_delete_with_id(self, doc, mock_repo):
        oid = ObjectId()
        doc.document_id = oid
        await doc.delete()
        mock_repo.delete_by_id.assert_awaited_once_with(oid)

    async def test_delete_without_id_does_nothing(
        self, doc, mock_repo
    ):
        await doc.delete()
        mock_repo.delete_by_id.assert_not_awaited()


class TestDocumentNotFoundError:
    """Tests for DocumentNotFoundError."""

    def test_raise_and_catch(self):
        with pytest.raises(DocumentNotFoundError):
            raise DocumentNotFoundError("gone")


class TestMongoRepository:
    """Tests for MongoRepository concrete implementation."""

    @pytest.fixture
    def repo(self, mock_mongo_client):
        return MongoRepository(mock_mongo_client, "test_db", "test_col")

    async def test_find_by_id(self, repo):
        oid = ObjectId()
        repo._collection.find_one = AsyncMock(
            return_value={"_id": oid}
        )
        result = await repo.find_by_id(oid)
        assert result["_id"] == oid

    async def test_find_one(self, repo):
        repo._collection.find_one = AsyncMock(
            return_value={"guild": 123}
        )
        result = await repo.find_one({"guild": 123})
        assert result["guild"] == 123

    async def test_insert(self, repo):
        oid = ObjectId()
        mock_result = MagicMock()
        mock_result.inserted_id = oid
        repo._collection.insert_one = AsyncMock(
            return_value=mock_result
        )
        result = await repo.insert({"data": "test"})
        assert result == oid

    async def test_delete_by_id(self, repo):
        oid = ObjectId()
        repo._collection.delete_one = AsyncMock()
        await repo.delete_by_id(oid)
        repo._collection.delete_one.assert_awaited_once_with(
            {"_id": oid}
        )
