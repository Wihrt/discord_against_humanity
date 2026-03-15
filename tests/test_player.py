"""Tests for MongoPlayer."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from bson.objectid import ObjectId

from discord_against_humanity.domain.player import MongoPlayer
from discord_against_humanity.infrastructure.mongo import Repository


@pytest.fixture
def mock_repo():
    """Create a mock Repository for player tests."""
    repo = MagicMock(spec=Repository)
    repo.find_by_id = AsyncMock(return_value=None)
    repo.find_one = AsyncMock(return_value=None)
    repo.insert = AsyncMock(return_value=ObjectId())
    repo.replace = AsyncMock(return_value={})
    repo.delete_by_id = AsyncMock()
    repo.aggregate = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def player(mock_mongo_client, mock_bot, mock_repo):
    """Create a MongoPlayer with default values set."""
    p = MongoPlayer(mock_mongo_client, repository=mock_repo)
    p._bot = mock_bot
    p._set_default_values()
    return p


class TestPlayerProperties:
    """Tests for MongoPlayer property getters and setters."""

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

    def test_white_cards_id_none_when_key_missing(self, mock_mongo_client, mock_bot):
        p = MongoPlayer(mock_mongo_client)
        p._bot = mock_bot
        assert p.white_cards_id is None

    def test_answers_id_default(self, player):
        assert player.answers_id == []

    def test_answers_id_none_when_key_missing(self, mock_mongo_client, mock_bot):
        p = MongoPlayer(mock_mongo_client)
        p._bot = mock_bot
        assert p.answers_id is None


class TestPlayerCreate:
    """Tests for MongoPlayer.create()."""

    async def test_create_sets_defaults(self, mock_bot, mock_mongo_client):
        mock_col = mock_mongo_client["cards_against_humanity"]["players"]
        mock_col.find_one = AsyncMock(return_value=None)

        player = await MongoPlayer.create(mock_bot, mock_mongo_client)
        assert player.score == 0
        assert player.white_cards_id == []
        assert player.answers_id == []

    async def test_create_with_document_id(self, mock_bot, mock_mongo_client):
        doc_id = ObjectId()
        mock_col = mock_mongo_client["cards_against_humanity"]["players"]
        mock_col.find_one = AsyncMock(
            return_value={
                "_id": doc_id,
                "guild": 1,
                "user": 2,
                "channel": 3,
                "score": 10,
                "answers": [],
                "white_cards": [],
                "tsar_choice": 0,
            }
        )

        player = await MongoPlayer.create(
            mock_bot, mock_mongo_client, document_id=doc_id
        )
        assert player.document_id == doc_id
        assert player.score == 10

    async def test_create_with_member_user(
        self, mock_bot, mock_mongo_client, mock_member
    ):
        mock_col = mock_mongo_client["cards_against_humanity"]["players"]
        mock_col.find_one = AsyncMock(
            return_value={
                "_id": ObjectId(),
                "guild": 1,
                "user": mock_member.id,
                "channel": 3,
                "score": 2,
                "answers": [],
                "white_cards": [],
                "tsar_choice": 0,
            }
        )

        player = await MongoPlayer.create(
            mock_bot, mock_mongo_client, user=mock_member
        )
        assert player.score == 2


class TestPlayerMethods:
    """Tests for MongoPlayer methods."""

    async def test_add_answers(self, player, mock_repo):
        card_ids = [ObjectId() for _ in range(5)]
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
        oid = ObjectId()
        player._document["_id"] = oid
        player._document["answers"] = [ObjectId(), ObjectId()]
        mock_repo.replace = AsyncMock(
            return_value=player._document
        )

        await player.delete_answers()

        assert player._document["answers"] == []

    async def test_delete_choice(self, player, mock_repo):
        oid = ObjectId()
        player._document["_id"] = oid
        player._document["tsar_choice"] = 3
        mock_repo.replace = AsyncMock(
            return_value=player._document
        )

        await player.delete_choice()

        assert player.tsar_choice == 0

    async def test_get_white_cards(self, player, mock_repo):
        card_ids = [ObjectId(), ObjectId()]
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
        answer_ids = [ObjectId()]
        player._document["answers"] = answer_ids
        mock_repo.find_by_id = AsyncMock(
            return_value={"_id": answer_ids[0], "text": "An answer"}
        )

        answers = await player.get_answers()

        assert len(answers) == 1
