"""Tests for ValkeyGame."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from discord_against_humanity.domain.game import ValkeyGame
from discord_against_humanity.infrastructure.valkey import Repository


@pytest.fixture
def mock_repo():
    """Create a mock Repository for game tests."""
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
def game(mock_valkey_client, mock_bot, mock_repo):
    """Create a ValkeyGame with default values set."""
    g = ValkeyGame(mock_valkey_client, repository=mock_repo)
    g._bot = mock_bot
    g._set_default_values()
    return g


class TestGameProperties:
    """Tests for ValkeyGame property getters and setters."""

    def test_guild_none_when_not_found(self, game):
        game._document["guild"] = 999
        game._bot.get_guild.return_value = None
        assert game.guild is None

    def test_guild_returns_guild(self, game, mock_guild):
        game._document["guild"] = mock_guild.id
        game._bot.get_guild.return_value = mock_guild
        assert game.guild is mock_guild

    def test_guild_setter(self, game, mock_guild):
        game.guild = mock_guild
        assert game._document["guild"] == mock_guild.id

    def test_guild_setter_rejects_wrong_type(self, game):
        with pytest.raises(TypeError):
            game.guild = "not a guild"

    def test_category_none_when_not_found(self, game, mock_guild):
        game._bot.get_guild.return_value = mock_guild
        game._document["guild"] = mock_guild.id
        mock_guild.get_channel.return_value = None
        assert game.category is None

    def test_category_returns_channel(self, game, mock_guild, mock_category_channel):
        game._bot.get_guild.return_value = mock_guild
        game._document["guild"] = mock_guild.id
        game._document["category"] = mock_category_channel.id
        mock_guild.get_channel.return_value = mock_category_channel
        assert game.category is mock_category_channel

    def test_category_setter(self, game, mock_category_channel):
        game.category = mock_category_channel
        assert game._document["category"] == mock_category_channel.id

    def test_category_setter_rejects_wrong_type(self, game):
        with pytest.raises(TypeError):
            game.category = "not a category"

    def test_board_none_when_not_found(self, game, mock_guild):
        game._bot.get_guild.return_value = mock_guild
        game._document["guild"] = mock_guild.id
        mock_guild.get_channel.return_value = None
        assert game.board is None

    def test_board_returns_channel(self, game, mock_guild, mock_text_channel):
        game._bot.get_guild.return_value = mock_guild
        game._document["guild"] = mock_guild.id
        game._document["board"] = mock_text_channel.id
        mock_guild.get_channel.return_value = mock_text_channel
        assert game.board is mock_text_channel

    def test_board_setter(self, game, mock_text_channel):
        game.board = mock_text_channel
        assert game._document["board"] == mock_text_channel.id

    def test_board_setter_rejects_wrong_type(self, game):
        with pytest.raises(TypeError):
            game.board = "not a channel"

    def test_points_default(self, game):
        assert game.points == 5

    def test_points_setter(self, game):
        game.points = 10
        assert game.points == 10

    def test_points_setter_rejects_wrong_type(self, game):
        with pytest.raises(TypeError):
            game.points = "ten"

    def test_playing_default(self, game):
        assert game.playing is False

    def test_playing_setter(self, game):
        game.playing = True
        assert game.playing is True

    def test_playing_setter_rejects_wrong_type(self, game):
        with pytest.raises(TypeError):
            game.playing = "yes"

    def test_voting_default(self, game):
        assert game.voting == "nobody"

    def test_voting_setter_valid(self, game):
        for val in ("players", "tsar", "nobody"):
            game.voting = val
            assert game.voting == val

    def test_voting_setter_rejects_wrong_type(self, game):
        with pytest.raises(TypeError):
            game.voting = 123

    def test_voting_setter_rejects_invalid_value(self, game):
        with pytest.raises(ValueError, match="Wrong value for voting"):
            game.voting = "invalid"

    def test_players_id_default(self, game):
        assert game.players_id == []

    def test_players_id_none_when_key_missing(self, mock_valkey_client, mock_bot):
        g = ValkeyGame(mock_valkey_client)
        g._bot = mock_bot
        assert g.players_id is None

    def test_black_cards_id_default(self, game):
        assert game.black_cards_id == []

    def test_white_cards_id_default(self, game):
        assert game.white_cards_id == []

    def test_tsar_id_default(self, game):
        assert game.tsar_id == 0


class TestGameCreate:
    """Tests for ValkeyGame.create()."""

    async def test_create_sets_defaults(self, mock_bot, mock_valkey_client, mock_guild):
        mock_repo = MagicMock(spec=Repository)
        mock_repo.find_one = AsyncMock(return_value=None)

        game = ValkeyGame(mock_valkey_client, repository=mock_repo)
        game._bot = mock_bot
        game._set_default_values()
        assert game.points == 5
        assert game.playing is False
        assert game.voting == "nobody"

    async def test_create_loads_existing_game(
        self, mock_bot, mock_valkey_client, mock_guild
    ):
        existing_doc = {
            "_id": str(uuid4()),
            "guild": mock_guild.id,
            "category": 0,
            "board": 0,
            "players": [str(uuid4())],
            "black_cards": [],
            "white_cards": [],
            "points": 10,
            "playing": True,
            "voting": "players",
            "results": [],
            "tsar": 0,
        }
        mock_repo = MagicMock(spec=Repository)
        mock_repo.find_one = AsyncMock(return_value=existing_doc)

        game = ValkeyGame(mock_valkey_client, repository=mock_repo)
        game._bot = mock_bot
        game._set_default_values()
        await game._get(mock_guild.id)
        assert game.points == 10
        assert game.playing is True
        assert game.voting == "players"


class TestGameMethods:
    """Tests for ValkeyGame methods."""

    async def test_add_player_type_check(self, game):
        with pytest.raises(TypeError, match="Wrong type for player"):
            await game.add_player("not a player")

    async def test_delete_player_type_check(self, game):
        with pytest.raises(TypeError, match="Wrong type for player"):
            await game.delete_player("not a player")

    async def test_add_player(
        self, game, mock_bot, mock_valkey_client, mock_repo
    ):
        from discord_against_humanity.domain.player import ValkeyPlayer

        player = ValkeyPlayer(mock_valkey_client, repository=mock_repo)
        player._bot = mock_bot
        player._set_default_values()
        player._document["_id"] = str(uuid4())

        # Mock save -> replace returns updated document
        game._repo.replace = AsyncMock(
            return_value=game._document
        )

        await game.add_player(player)

        assert player.document_id in game._document["players"]

    async def test_delete_player(
        self, game, mock_bot, mock_valkey_client, mock_repo
    ):
        from discord_against_humanity.domain.player import ValkeyPlayer

        game._document["_id"] = str(uuid4())

        player = ValkeyPlayer(mock_valkey_client, repository=mock_repo)
        player._bot = mock_bot
        player._set_default_values()
        pid = str(uuid4())
        player._document["_id"] = pid
        game._document["players"].append(pid)

        game._repo.replace = AsyncMock(
            return_value=game._document
        )

        await game.delete_player(player)

        assert pid not in game._document["players"]

    async def test_get_players_answers_counts_non_tsar(
        self, game, mock_bot, mock_valkey_client
    ):
        tsar_id = str(uuid4())
        player1_id = str(uuid4())
        player2_id = str(uuid4())
        game._document["players"] = [tsar_id, player1_id, player2_id]
        game._document["tsar"] = tsar_id

        # Patch ValkeyPlayer.create to return mock players
        async def fake_create(bot, client, doc_id):
            from discord_against_humanity.domain.player import ValkeyPlayer

            p = ValkeyPlayer(client)
            p._bot = bot
            p._set_default_values()
            p._document["_id"] = doc_id
            if doc_id == player1_id:
                p._document["answers"] = [str(uuid4())]
            # player2 has no answers (empty list)
            return p

        with patch(
            "discord_against_humanity.domain.game.ValkeyPlayer.create",
            side_effect=fake_create,
        ):
            count = await game.get_players_answers()
            assert count == 1

    async def test_get_players_score(self, game, mock_bot, mock_valkey_client):
        p1_id = str(uuid4())
        p2_id = str(uuid4())
        game._document["players"] = [p1_id, p2_id]

        async def fake_create(bot, client, doc_id):
            from discord_against_humanity.domain.player import ValkeyPlayer

            p = ValkeyPlayer(client)
            p._bot = bot
            p._set_default_values()
            p._document["_id"] = doc_id
            if doc_id == p1_id:
                p._document["score"] = 3
            else:
                p._document["score"] = 1
            return p

        with patch(
            "discord_against_humanity.domain.game.ValkeyPlayer.create",
            side_effect=fake_create,
        ):
            scores = await game.get_players_score()
            assert len(scores) == 2
            score_values = [s[1] for s in scores]
            assert 3 in score_values
            assert 1 in score_values

    async def test_is_points_max_false(self, game, mock_bot, mock_valkey_client):
        p1_id = str(uuid4())
        game._document["players"] = [p1_id]
        game._document["points"] = 5

        async def fake_create(bot, client, doc_id):
            from discord_against_humanity.domain.player import ValkeyPlayer

            p = ValkeyPlayer(client)
            p._bot = bot
            p._set_default_values()
            p._document["_id"] = doc_id
            p._document["score"] = 2
            return p

        with patch(
            "discord_against_humanity.domain.game.ValkeyPlayer.create",
            side_effect=fake_create,
        ):
            result = await game.is_points_max()
            assert result is False

    async def test_is_points_max_true(self, game, mock_bot, mock_valkey_client):
        p1_id = str(uuid4())
        game._document["players"] = [p1_id]
        game._document["points"] = 5

        async def fake_create(bot, client, doc_id):
            from discord_against_humanity.domain.player import ValkeyPlayer

            p = ValkeyPlayer(client)
            p._bot = bot
            p._set_default_values()
            p._document["_id"] = doc_id
            p._document["score"] = 5
            return p

        with patch(
            "discord_against_humanity.domain.game.ValkeyPlayer.create",
            side_effect=fake_create,
        ):
            result = await game.is_points_max()
            assert result is True

    async def test_set_random_tsar(self, game):
        game._document["_id"] = str(uuid4())
        ids = [str(uuid4()), str(uuid4()), str(uuid4())]
        game._document["players"] = ids
        game._repo.replace = AsyncMock(
            return_value=game._document
        )

        await game.set_random_tsar()

        assert game._document["tsar"] in ids

    async def test_set_random_tsar_empty_players(self, game):
        """Guard: set_random_tsar does nothing with no players."""
        game._document["players"] = []
        await game.set_random_tsar()
        assert game._document["tsar"] == 0

    async def test_get_tsar_answer_true(self, game, mock_bot, mock_valkey_client):
        tsar_id = str(uuid4())
        game._document["tsar"] = tsar_id

        async def fake_create(bot, client, doc_id):
            from discord_against_humanity.domain.player import ValkeyPlayer

            p = ValkeyPlayer(client)
            p._bot = bot
            p._set_default_values()
            p._document["_id"] = doc_id
            p._document["tsar_choice"] = 2
            return p

        with patch(
            "discord_against_humanity.domain.game.ValkeyPlayer.create",
            side_effect=fake_create,
        ):
            result = await game.get_tsar_answer()
            assert result is True

    async def test_get_tsar_answer_false(self, game, mock_bot, mock_valkey_client):
        tsar_id = str(uuid4())
        game._document["tsar"] = tsar_id

        async def fake_create(bot, client, doc_id):
            from discord_against_humanity.domain.player import ValkeyPlayer

            p = ValkeyPlayer(client)
            p._bot = bot
            p._set_default_values()
            p._document["_id"] = doc_id
            p._document["tsar_choice"] = 0
            return p

        with patch(
            "discord_against_humanity.domain.game.ValkeyPlayer.create",
            side_effect=fake_create,
        ):
            result = await game.get_tsar_answer()
            assert result is False


class TestGameDefaultValues:
    """Tests for _set_default_values()."""

    def test_default_values(self, game):
        assert game._document["guild"] == 0
        assert game._document["category"] == 0
        assert game._document["board"] == 0
        assert game._document["players"] == []
        assert game._document["black_cards"] == []
        assert game._document["white_cards"] == []
        assert game._document["points"] == 5
        assert game._document["playing"] is False
        assert game._document["voting"] == "nobody"
        assert game._document["results"] == []
        assert game._document["tsar"] == 0
