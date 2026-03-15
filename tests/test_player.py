"""Tests for ValkeyPlayer."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from discord_against_humanity.domain.player import ValkeyPlayer
from discord_against_humanity.infrastructure.valkey import Repository


@pytest.fixture
def mock_repo():
    """Create a mock Repository for player tests."""
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
def player(mock_valkey_client, mock_bot, mock_repo):
    """Create a ValkeyPlayer with default values set."""
    p = ValkeyPlayer(mock_valkey_client, repository=mock_repo)
    p._bot = mock_bot
    p._set_default_values()
    return p


class TestPlayerProperties:
    """Tests for ValkeyPlayer property getters and setters."""

    def test_guild_none_when_not_found(self, player):
        player._document["guild"] = 999
        player._bot.get_guild.return_value = None
        assert player.guild is None

    def test_guild_returns_guild(self, player, mock_guild):
        player._document["guild"] = mock_guild.id
        player._bot.get_guild.return_value = mock_guild
        assert player.guild is mock_guild

    def test_guild_setter(self, player, mock_guild):
        player.guild = mock_guild
        assert player._document["guild"] == mock_guild.id

    def test_guild_setter_rejects_wrong_type(self, player):
        with pytest.raises(TypeError):
            player.guild = "not a guild"

    def test_user_none_when_empty(self, player, mock_guild):
        player._bot.get_guild.return_value = mock_guild
        player._document["guild"] = mock_guild.id
        mock_guild.get_member.return_value = None
        assert player.user is None

    def test_user_returns_member(self, player, mock_guild, mock_member):
        player._bot.get_guild.return_value = mock_guild
        player._document["guild"] = mock_guild.id
        player._document["user"] = mock_member.id
        mock_guild.get_member.return_value = mock_member
        assert player.user is mock_member

    def test_user_setter(self, player, mock_member):
        player.user = mock_member
        assert player._document["user"] == mock_member.id

    def test_user_setter_rejects_wrong_type(self, player):
        with pytest.raises(TypeError):
            player.user = "not a member"

    def test_channel_none_when_empty(self, player, mock_guild):
        player._bot.get_guild.return_value = mock_guild
        player._document["guild"] = mock_guild.id
        mock_guild.get_channel.return_value = None
        assert player.channel is None

    def test_channel_returns_channel(self, player, mock_guild, mock_text_channel):
        player._bot.get_guild.return_value = mock_guild
        player._document["guild"] = mock_guild.id
        player._document["channel"] = mock_text_channel.id
        mock_guild.get_channel.return_value = mock_text_channel
        assert player.channel is mock_text_channel

    def test_channel_setter(self, player, mock_text_channel):
        player.channel = mock_text_channel
        assert player._document["channel"] == mock_text_channel.id

    def test_channel_setter_rejects_wrong_type(self, player):
        with pytest.raises(TypeError):
            player.channel = "not a channel"

    def test_score_default(self, player):
        assert player.score == 0

    def test_score_setter(self, player):
        player.score = 5
        assert player.score == 5

    def test_score_setter_rejects_wrong_type(self, player):
        with pytest.raises(TypeError):
            player.score = "not an int"

    def test_tsar_choice_default(self, player):
        assert player.tsar_choice == 0

    def test_tsar_choice_setter(self, player):
        player.tsar_choice = 3
        assert player.tsar_choice == 3

    def test_tsar_choice_setter_rejects_wrong_type(self, player):
        with pytest.raises(TypeError):
            player.tsar_choice = "nope"

    def test_white_cards_id_default(self, player):
        assert player.white_cards_id == []

    def test_white_cards_id_none_when_key_missing(self, mock_valkey_client, mock_bot):
        p = ValkeyPlayer(mock_valkey_client)
        p._bot = mock_bot
        assert p.white_cards_id is None

    def test_answers_id_default(self, player):
        assert player.answers_id == []

    def test_answers_id_none_when_key_missing(self, mock_valkey_client, mock_bot):
        p = ValkeyPlayer(mock_valkey_client)
        p._bot = mock_bot
        assert p.answers_id is None


class TestPlayerCreate:
    """Tests for ValkeyPlayer.create()."""

    async def test_create_sets_defaults(self, mock_bot, mock_valkey_client):
        mock_repo = MagicMock(spec=Repository)
        mock_repo.find_one = AsyncMock(return_value=None)

        player = ValkeyPlayer(mock_valkey_client, repository=mock_repo)
        player._bot = mock_bot
        player._set_default_values()
        assert player.score == 0
        assert player.white_cards_id == []
        assert player.answers_id == []

    async def test_create_with_document_id(self, mock_bot, mock_valkey_client):
        import json

        doc_id = str(uuid4())
        doc_data = {
            "guild": 1,
            "user": 2,
            "channel": 3,
            "score": 10,
            "answers": [],
            "white_cards": [],
            "tsar_choice": 0,
        }
        # The ValkeyRepository will call client.get() to find the document
        mock_valkey_client.get = AsyncMock(
            return_value=json.dumps(doc_data)
        )

        player = await ValkeyPlayer.create(
            mock_bot, mock_valkey_client, document_id=doc_id
        )
        assert player.document_id == doc_id
        assert player.score == 10

    async def test_create_with_member_user(
        self, mock_bot, mock_valkey_client, mock_member
    ):
        mock_repo = MagicMock(spec=Repository)
        mock_repo.find_one = AsyncMock(
            return_value={
                "_id": str(uuid4()),
                "guild": 1,
                "user": mock_member.id,
                "channel": 3,
                "score": 2,
                "answers": [],
                "white_cards": [],
                "tsar_choice": 0,
            }
        )
        mock_repo.find_by_id = AsyncMock(return_value=None)

        player = ValkeyPlayer(mock_valkey_client, repository=mock_repo)
        player._bot = mock_bot
        player._set_default_values()
        await player._get(mock_member)
        assert player.score == 2


class TestPlayerMethods:
    """Tests for ValkeyPlayer methods."""

    async def test_add_answers(self, player, mock_repo):
        card_ids = [str(uuid4()) for _ in range(5)]
        player._document["white_cards"] = list(card_ids)
        mock_repo.replace = AsyncMock(
            return_value=player._document
        )

        # Pick cards at indices 1 and 3 (1-based)
        await player.add_answers([1, 3])

        assert card_ids[0] in player._document["answers"]
        assert card_ids[2] in player._document["answers"]
        assert len(player._document["answers"]) == 2

    async def test_delete_answers(self, player, mock_repo):
        doc_id = str(uuid4())
        player._document["_id"] = doc_id
        player._document["answers"] = [str(uuid4()), str(uuid4())]
        mock_repo.replace = AsyncMock(
            return_value=player._document
        )

        await player.delete_answers()

        assert player._document["answers"] == []

    async def test_delete_choice(self, player, mock_repo):
        doc_id = str(uuid4())
        player._document["_id"] = doc_id
        player._document["tsar_choice"] = 3
        mock_repo.replace = AsyncMock(
            return_value=player._document
        )

        await player.delete_choice()

        assert player.tsar_choice == 0

    async def test_get_white_cards(self, player, mock_repo):
        card_ids = [str(uuid4()), str(uuid4())]
        player._document["white_cards"] = card_ids
        mock_repo.find_by_id = AsyncMock(
            side_effect=[
                {"_id": card_ids[0], "text": "Card A"},
                {"_id": card_ids[1], "text": "Card B"},
            ]
        )

        cards = await player.get_white_cards()

        assert len(cards) == 2

    async def test_get_answers(self, player, mock_repo):
        answer_ids = [str(uuid4())]
        player._document["answers"] = answer_ids
        mock_repo.find_by_id = AsyncMock(
            return_value={"_id": answer_ids[0], "text": "An answer"}
        )

        answers = await player.get_answers()

        assert len(answers) == 1
