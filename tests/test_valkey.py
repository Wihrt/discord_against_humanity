"""Tests for the Document base class and Repository pattern."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from discord_against_humanity.domain.document import Document
from discord_against_humanity.ports.repository import (
    DocumentNotFoundError,
    Repository,
)
from discord_against_humanity.ports.valkey import ValkeyRepository


class ConcreteDocument(Document):
    """Concrete subclass for testing the abstract Document."""

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
    repo.insert = AsyncMock(return_value=str(uuid4()))
    repo.replace = AsyncMock(return_value={})
    repo.delete_by_id = AsyncMock()
    repo.random_member = AsyncMock(return_value=None)
    repo.count = AsyncMock(return_value=0)
    return repo


@pytest.fixture
def mock_factory(mock_repo):
    """Create a mock RepositoryFactory."""
    return MagicMock(side_effect=lambda _: mock_repo)


@pytest.fixture
def doc(mock_repo, mock_factory):
    """Create a ConcreteDocument with a mock repo."""
    return ConcreteDocument(repository=mock_repo, repo_factory=mock_factory)


class TestDocumentId:
    """Tests for document_id property."""

    def test_document_id_none_when_empty(self, doc):
        assert doc.document_id is None

    def test_document_id_getter(self, doc):
        doc_id = str(uuid4())
        doc._document["_id"] = doc_id
        assert doc.document_id == doc_id

    def test_document_id_setter(self, doc):
        doc_id = str(uuid4())
        doc.document_id = doc_id
        assert doc._document["_id"] == doc_id

    def test_document_id_setter_rejects_non_str(self, doc):
        with pytest.raises(
            TypeError, match="document_id must be a str"
        ):
            doc.document_id = 12345

    def test_document_id_setter_rejects_int(self, doc):
        with pytest.raises(TypeError):
            doc.document_id = 12345


class TestInit:
    """Tests for __init__ and class attributes."""

    def test_collection(self):
        assert ConcreteDocument._COLLECTION == "test_collection"

    def test_repo_stored(self, doc, mock_repo):
        assert doc._repo is mock_repo

    def test_empty_document(self, doc):
        assert doc._document == {}

    def test_raises_if_collection_not_set(self, mock_repo, mock_factory):
        class BadDoc(Document):
            _COLLECTION = ""

            @classmethod
            async def create(cls):
                raise NotImplementedError

        with pytest.raises(ValueError, match="must define"):
            BadDoc(repository=mock_repo, repo_factory=mock_factory)

    def test_custom_repository_used(self, mock_repo, mock_factory):
        doc = ConcreteDocument(
            repository=mock_repo, repo_factory=mock_factory
        )
        assert doc._repo is mock_repo


class TestGet:
    """Tests for the get() method."""

    async def test_get_does_nothing_when_no_id(self, doc, mock_repo):
        await doc.get()
        mock_repo.find_by_id.assert_not_awaited()

    async def test_get_uses_current_id(self, doc, mock_repo):
        doc_id = str(uuid4())
        doc._document["_id"] = doc_id
        mock_repo.find_by_id = AsyncMock(
            return_value={"_id": doc_id, "data": "value"}
        )
        await doc.get()
        mock_repo.find_by_id.assert_awaited_once_with(doc_id)
        assert doc._document["data"] == "value"

    async def test_get_with_explicit_id(self, doc, mock_repo):
        other_id = str(uuid4())
        mock_repo.find_by_id = AsyncMock(
            return_value={"_id": other_id, "key": "val"}
        )
        await doc.get(other_id)
        mock_repo.find_by_id.assert_awaited_once_with(other_id)
        assert doc._document["key"] == "val"

    async def test_get_leaves_document_unchanged_on_not_found(
        self, doc, mock_repo
    ):
        doc_id = str(uuid4())
        doc._document = {"_id": doc_id, "existing": "data"}
        mock_repo.find_by_id = AsyncMock(return_value=None)
        await doc.get(doc_id)
        assert doc._document["existing"] == "data"


class TestSave:
    """Tests for the save() method."""

    async def test_save_insert_new_document(self, doc, mock_repo):
        new_id = str(uuid4())
        mock_repo.insert = AsyncMock(return_value=new_id)
        await doc.save()
        mock_repo.insert.assert_awaited_once()
        assert doc.document_id == new_id

    async def test_save_replaces_existing_document(
        self, doc, mock_repo
    ):
        doc_id = str(uuid4())
        doc.document_id = doc_id
        doc._document["field"] = "updated"
        replaced = {"_id": doc_id, "field": "updated"}
        mock_repo.replace = AsyncMock(return_value=replaced)
        await doc.save()
        mock_repo.replace.assert_awaited_once_with(
            doc_id, doc._document
        )


class TestDelete:
    """Tests for the delete() method."""

    async def test_delete_with_id(self, doc, mock_repo):
        doc_id = str(uuid4())
        doc.document_id = doc_id
        await doc.delete()
        mock_repo.delete_by_id.assert_awaited_once_with(doc_id)

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


class TestValkeyRepository:
    """Tests for ValkeyRepository concrete implementation."""

    @pytest.fixture
    def repo(self, mock_valkey_client):
        return ValkeyRepository(mock_valkey_client, "test_col")

    async def test_find_by_id(self, repo):
        import json

        doc_id = str(uuid4())
        repo._client.get = AsyncMock(
            return_value=json.dumps({"field": "value"})
        )
        result = await repo.find_by_id(doc_id)
        assert result["_id"] == doc_id
        assert result["field"] == "value"

    async def test_find_by_id_returns_none(self, repo):
        repo._client.get = AsyncMock(return_value=None)
        result = await repo.find_by_id(str(uuid4()))
        assert result is None

    async def test_insert(self, repo):
        result = await repo.insert({"data": "test"})
        assert isinstance(result, str)
        repo._client.set.assert_awaited()
        repo._client.sadd.assert_awaited()

    async def test_delete_by_id(self, repo):
        doc_id = str(uuid4())
        repo._client.get = AsyncMock(return_value=None)
        await repo.delete_by_id(doc_id)
        repo._client.delete.assert_awaited()
        repo._client.srem.assert_awaited()
