"""Tests for the MongoDocument base class."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from bson.objectid import ObjectId

from discord_against_humanity.infrastructure.mongo import MongoDocument


class ConcreteDocument(MongoDocument):
    """Concrete subclass for testing the abstract MongoDocument."""

    _DATABASE = "test_db"
    _COLLECTION = "test_collection"

    @classmethod
    async def create(cls):
        raise NotImplementedError


@pytest.fixture
def doc(mock_mongo_client):
    """Create a ConcreteDocument instance with a mock client."""
    return ConcreteDocument(mock_mongo_client)


@pytest.fixture
def mock_col(doc):
    """Return the mock collection bound to the document."""
    return doc._collection


class TestDocumentId:
    """Tests for document_id property."""

    def test_document_id_none_when_empty(self, doc):
        assert doc.document_id is None

    def test_document_id_getter(self, doc, sample_object_id):
        doc._document["_id"] = sample_object_id
        assert doc.document_id == sample_object_id

    def test_document_id_setter(self, doc, sample_object_id):
        doc.document_id = sample_object_id
        assert doc._document["_id"] == sample_object_id

    def test_document_id_setter_rejects_non_objectid(self, doc):
        with pytest.raises(TypeError, match="document_id must be an ObjectId"):
            doc.document_id = "not-an-objectid"

    def test_document_id_setter_rejects_int(self, doc):
        with pytest.raises(TypeError):
            doc.document_id = 12345


class TestGet:
    """Tests for the get() method."""

    async def test_get_uses_current_id(self, doc, mock_col, sample_object_id):
        doc._document["_id"] = sample_object_id
        mock_col.find_one = AsyncMock(
            return_value={"_id": sample_object_id, "data": "value"}
        )

        await doc.get()

        mock_col.find_one.assert_awaited_once_with({"_id": sample_object_id})
        assert doc._document["data"] == "value"

    async def test_get_with_explicit_id(self, doc, mock_col, sample_object_id):
        other_id = ObjectId()
        mock_col.find_one = AsyncMock(
            return_value={"_id": other_id, "key": "val"}
        )

        await doc.get(other_id)

        mock_col.find_one.assert_awaited_once_with({"_id": other_id})
        assert doc._document["key"] == "val"


class TestSave:
    """Tests for the save() method."""

    async def test_save_insert_new_document(self, doc, mock_col):
        insert_result = MagicMock()
        insert_result.inserted_id = ObjectId()
        mock_col.insert_one = AsyncMock(return_value=insert_result)
        mock_col.find_one = AsyncMock(
            return_value={"_id": insert_result.inserted_id, "data": "saved"}
        )

        await doc.save()

        mock_col.insert_one.assert_awaited_once()
        assert doc.document_id == insert_result.inserted_id

    async def test_save_replaces_existing_document(self, doc, mock_col, sample_object_id):
        doc.document_id = sample_object_id
        doc._document["field"] = "updated"
        replaced = {"_id": sample_object_id, "field": "updated"}
        mock_col.find_one_and_replace = AsyncMock(return_value=replaced)
        mock_col.find_one = AsyncMock(return_value=replaced)

        await doc.save()

        mock_col.find_one_and_replace.assert_awaited_once()
        mock_col.insert_one.assert_not_awaited()


class TestDelete:
    """Tests for the delete() method."""

    async def test_delete_with_id(self, doc, mock_col, sample_object_id):
        doc.document_id = sample_object_id
        mock_col.delete_one = AsyncMock()

        await doc.delete()

        mock_col.delete_one.assert_awaited_once_with({"_id": sample_object_id})

    async def test_delete_without_id_does_nothing(self, doc, mock_col):
        mock_col.delete_one = AsyncMock()

        await doc.delete()

        mock_col.delete_one.assert_not_awaited()


class TestInit:
    """Tests for __init__ and class attributes."""

    def test_database_and_collection(self):
        assert ConcreteDocument._DATABASE == "test_db"
        assert ConcreteDocument._COLLECTION == "test_collection"

    def test_client_stored(self, doc, mock_mongo_client):
        assert doc._client is mock_mongo_client

    def test_empty_document(self, doc):
        assert doc._document == {}
