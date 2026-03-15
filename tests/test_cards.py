"""Tests for BlackCard and WhiteCard."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from discord_against_humanity.domain.cards import BlackCard, WhiteCard
from discord_against_humanity.ports.repository import Repository


class TestBlackCard:
    """Tests for BlackCard."""

    def test_collection(self, mock_repo, mock_repo_factory):
        card = BlackCard(repository=mock_repo, repo_factory=mock_repo_factory)
        assert card._COLLECTION == "black_cards"

    def test_text_none_when_empty(self, mock_repo, mock_repo_factory):
        card = BlackCard(repository=mock_repo, repo_factory=mock_repo_factory)
        assert card.text is None

    def test_text_with_underscore_replaces_blanks(self, mock_repo, mock_repo_factory):
        card = BlackCard(repository=mock_repo, repo_factory=mock_repo_factory)
        card._document = {"text": "Why did _ go to _?", "pick": 2}
        result = card.text
        assert "{}" in result
        assert "_" not in result

    def test_text_without_underscore_appends_blanks(self, mock_repo, mock_repo_factory):
        card = BlackCard(repository=mock_repo, repo_factory=mock_repo_factory)
        card._document = {"text": "What is love?", "pick": 1}
        result = card.text
        assert "{}" in result

    def test_text_html_is_converted(self, mock_repo, mock_repo_factory):
        card = BlackCard(repository=mock_repo, repo_factory=mock_repo_factory)
        card._document = {"text": "<b>Bold _</b>", "pick": 1}
        result = card.text
        # html2text converts <b> to ** markers
        assert result is not None
        assert "<b>" not in result

    def test_pick_defaults_to_one_when_empty(self, mock_repo, mock_repo_factory):
        card = BlackCard(repository=mock_repo, repo_factory=mock_repo_factory)
        assert card.pick == 1

    def test_pick_returns_value(self, mock_repo, mock_repo_factory):
        card = BlackCard(repository=mock_repo, repo_factory=mock_repo_factory)
        card._document = {"pick": 2}
        assert card.pick == 2

    async def test_create_without_document_id(self, mock_repo_factory):
        card = await BlackCard.create(mock_repo_factory)
        assert isinstance(card, BlackCard)
        assert card.document_id is None

    async def test_create_with_document_id(self, mock_repo_factory):
        doc_id = str(uuid4())
        mock_repo = MagicMock(spec=Repository)
        mock_repo.find_by_id = AsyncMock(
            return_value={"_id": doc_id, "text": "Test _", "pick": 1}
        )

        card = BlackCard(repository=mock_repo, repo_factory=mock_repo_factory)
        await card.get(doc_id)
        assert card._document["_id"] == doc_id
        assert card._document["text"] == "Test _"


class TestWhiteCard:
    """Tests for WhiteCard."""

    def test_collection(self, mock_repo, mock_repo_factory):
        card = WhiteCard(repository=mock_repo, repo_factory=mock_repo_factory)
        assert card._COLLECTION == "white_cards"

    def test_text_none_when_empty(self, mock_repo, mock_repo_factory):
        card = WhiteCard(repository=mock_repo, repo_factory=mock_repo_factory)
        assert card.text is None

    def test_text_returns_stripped_html(self, mock_repo, mock_repo_factory):
        card = WhiteCard(repository=mock_repo, repo_factory=mock_repo_factory)
        card._document = {"text": "<i>Something funny</i>"}
        result = card.text
        assert result is not None
        assert "<i>" not in result
        assert "Something funny" in result

    def test_text_strips_trailing_whitespace(self, mock_repo, mock_repo_factory):
        card = WhiteCard(repository=mock_repo, repo_factory=mock_repo_factory)
        card._document = {"text": "Answer text"}
        result = card.text
        assert result == result.rstrip()

    async def test_create_without_document_id(self, mock_repo_factory):
        card = await WhiteCard.create(mock_repo_factory)
        assert isinstance(card, WhiteCard)
        assert card.document_id is None

    async def test_create_with_document_id(self, mock_repo_factory):
        doc_id = str(uuid4())
        mock_repo = MagicMock(spec=Repository)
        mock_repo.find_by_id = AsyncMock(
            return_value={"_id": doc_id, "text": "A witty answer"}
        )

        card = WhiteCard(repository=mock_repo, repo_factory=mock_repo_factory)
        await card.get(doc_id)
        assert card._document["_id"] == doc_id
        assert card._document["text"] == "A witty answer"
