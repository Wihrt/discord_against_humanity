"""Tests for MongoBlackCard and MongoWhiteCard."""

from unittest.mock import AsyncMock

from bson.objectid import ObjectId

from discord_against_humanity.domain.cards import MongoBlackCard, MongoWhiteCard


class TestMongoBlackCard:
    """Tests for MongoBlackCard."""

    def test_database_and_collection(self, mock_mongo_client):
        card = MongoBlackCard(mock_mongo_client)
        assert card._DATABASE == "cards_against_humanity"
        assert card._COLLECTION == "black_cards"

    def test_text_none_when_empty(self, mock_mongo_client):
        card = MongoBlackCard(mock_mongo_client)
        assert card.text is None

    def test_text_with_underscore_replaces_blanks(self, mock_mongo_client):
        card = MongoBlackCard(mock_mongo_client)
        card._document = {"text": "Why did _ go to _?", "pick": 2}
        result = card.text
        assert "{}" in result
        assert "_" not in result

    def test_text_without_underscore_appends_blanks(self, mock_mongo_client):
        card = MongoBlackCard(mock_mongo_client)
        card._document = {"text": "What is love?", "pick": 1}
        result = card.text
        assert "{}" in result

    def test_text_html_is_converted(self, mock_mongo_client):
        card = MongoBlackCard(mock_mongo_client)
        card._document = {"text": "<b>Bold _</b>", "pick": 1}
        result = card.text
        # html2text converts <b> to ** markers
        assert result is not None
        assert "<b>" not in result

    def test_pick_defaults_to_one_when_empty(self, mock_mongo_client):
        card = MongoBlackCard(mock_mongo_client)
        assert card.pick == 1

    def test_pick_returns_value(self, mock_mongo_client):
        card = MongoBlackCard(mock_mongo_client)
        card._document = {"pick": 2}
        assert card.pick == 2

    async def test_create_without_document_id(self, mock_mongo_client):
        card = await MongoBlackCard.create(mock_mongo_client)
        assert isinstance(card, MongoBlackCard)
        assert card.document_id is None

    async def test_create_with_document_id(self, mock_mongo_client):
        doc_id = ObjectId()
        mock_col = mock_mongo_client["cards_against_humanity"]["black_cards"]
        mock_col.find_one = AsyncMock(
            return_value={"_id": doc_id, "text": "Test _", "pick": 1}
        )

        card = await MongoBlackCard.create(mock_mongo_client, doc_id)
        assert card._document["_id"] == doc_id
        assert card._document["text"] == "Test _"


class TestMongoWhiteCard:
    """Tests for MongoWhiteCard."""

    def test_database_and_collection(self, mock_mongo_client):
        card = MongoWhiteCard(mock_mongo_client)
        assert card._DATABASE == "cards_against_humanity"
        assert card._COLLECTION == "white_cards"

    def test_text_none_when_empty(self, mock_mongo_client):
        card = MongoWhiteCard(mock_mongo_client)
        assert card.text is None

    def test_text_returns_stripped_html(self, mock_mongo_client):
        card = MongoWhiteCard(mock_mongo_client)
        card._document = {"text": "<i>Something funny</i>"}
        result = card.text
        assert result is not None
        assert "<i>" not in result
        assert "Something funny" in result

    def test_text_strips_trailing_whitespace(self, mock_mongo_client):
        card = MongoWhiteCard(mock_mongo_client)
        card._document = {"text": "Answer text"}
        result = card.text
        assert result == result.rstrip()

    async def test_create_without_document_id(self, mock_mongo_client):
        card = await MongoWhiteCard.create(mock_mongo_client)
        assert isinstance(card, MongoWhiteCard)
        assert card.document_id is None

    async def test_create_with_document_id(self, mock_mongo_client):
        doc_id = ObjectId()
        mock_col = mock_mongo_client["cards_against_humanity"]["white_cards"]
        mock_col.find_one = AsyncMock(
            return_value={"_id": doc_id, "text": "A witty answer"}
        )

        card = await MongoWhiteCard.create(mock_mongo_client, doc_id)
        assert card._document["_id"] == doc_id
        assert card._document["text"] == "A witty answer"
