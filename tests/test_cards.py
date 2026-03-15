"""Tests for ValkeyBlackCard and ValkeyWhiteCard."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from discord_against_humanity.domain.cards import ValkeyBlackCard, ValkeyWhiteCard
from discord_against_humanity.infrastructure.valkey import Repository


class TestValkeyBlackCard:
    """Tests for ValkeyBlackCard."""

    def test_collection(self, mock_valkey_client):
        card = ValkeyBlackCard(mock_valkey_client)
        assert card._COLLECTION == "black_cards"

    def test_text_none_when_empty(self, mock_valkey_client):
        card = ValkeyBlackCard(mock_valkey_client)
        assert card.text is None

    def test_text_with_underscore_replaces_blanks(self, mock_valkey_client):
        card = ValkeyBlackCard(mock_valkey_client)
        card._document = {"text": "Why did _ go to _?", "pick": 2}
        result = card.text
        assert "{}" in result
        assert "_" not in result

    def test_text_without_underscore_appends_blanks(self, mock_valkey_client):
        card = ValkeyBlackCard(mock_valkey_client)
        card._document = {"text": "What is love?", "pick": 1}
        result = card.text
        assert "{}" in result

    def test_text_html_is_converted(self, mock_valkey_client):
        card = ValkeyBlackCard(mock_valkey_client)
        card._document = {"text": "<b>Bold _</b>", "pick": 1}
        result = card.text
        # html2text converts <b> to ** markers
        assert result is not None
        assert "<b>" not in result

    def test_pick_defaults_to_one_when_empty(self, mock_valkey_client):
        card = ValkeyBlackCard(mock_valkey_client)
        assert card.pick == 1

    def test_pick_returns_value(self, mock_valkey_client):
        card = ValkeyBlackCard(mock_valkey_client)
        card._document = {"pick": 2}
        assert card.pick == 2

    async def test_create_without_document_id(self, mock_valkey_client):
        card = await ValkeyBlackCard.create(mock_valkey_client)
        assert isinstance(card, ValkeyBlackCard)
        assert card.document_id is None

    async def test_create_with_document_id(self, mock_valkey_client):
        import json

        doc_id = str(uuid4())
        mock_repo = MagicMock(spec=Repository)
        mock_repo.find_by_id = AsyncMock(
            return_value={"_id": doc_id, "text": "Test _", "pick": 1}
        )

        card = ValkeyBlackCard(mock_valkey_client, repository=mock_repo)
        await card.get(doc_id)
        assert card._document["_id"] == doc_id
        assert card._document["text"] == "Test _"


class TestValkeyWhiteCard:
    """Tests for ValkeyWhiteCard."""

    def test_collection(self, mock_valkey_client):
        card = ValkeyWhiteCard(mock_valkey_client)
        assert card._COLLECTION == "white_cards"

    def test_text_none_when_empty(self, mock_valkey_client):
        card = ValkeyWhiteCard(mock_valkey_client)
        assert card.text is None

    def test_text_returns_stripped_html(self, mock_valkey_client):
        card = ValkeyWhiteCard(mock_valkey_client)
        card._document = {"text": "<i>Something funny</i>"}
        result = card.text
        assert result is not None
        assert "<i>" not in result
        assert "Something funny" in result

    def test_text_strips_trailing_whitespace(self, mock_valkey_client):
        card = ValkeyWhiteCard(mock_valkey_client)
        card._document = {"text": "Answer text"}
        result = card.text
        assert result == result.rstrip()

    async def test_create_without_document_id(self, mock_valkey_client):
        card = await ValkeyWhiteCard.create(mock_valkey_client)
        assert isinstance(card, ValkeyWhiteCard)
        assert card.document_id is None

    async def test_create_with_document_id(self, mock_valkey_client):
        doc_id = str(uuid4())
        mock_repo = MagicMock(spec=Repository)
        mock_repo.find_by_id = AsyncMock(
            return_value={"_id": doc_id, "text": "A witty answer"}
        )

        card = ValkeyWhiteCard(mock_valkey_client, repository=mock_repo)
        await card.get(doc_id)
        assert card._document["_id"] == doc_id
        assert card._document["text"] == "A witty answer"
