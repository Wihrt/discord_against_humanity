"""Tests for bot creation and configuration."""

from unittest.mock import patch

from discord.ext.commands import Bot

from discord_against_humanity.bot import create_bot, init_logger


class TestCreateBot:
    """Tests for create_bot()."""

    @patch("discord_against_humanity.bot.valkey.Valkey")
    def test_returns_bot_instance(self, mock_valkey):
        bot = create_bot()
        assert isinstance(bot, Bot)

    @patch("discord_against_humanity.bot.valkey.Valkey")
    def test_command_prefix(self, mock_valkey):
        bot = create_bot()
        assert bot.command_prefix == "!"

    @patch("discord_against_humanity.bot.valkey.Valkey")
    def test_intents_message_content(self, mock_valkey):
        bot = create_bot()
        assert bot.intents.message_content is True

    @patch("discord_against_humanity.bot.valkey.Valkey")
    def test_intents_members(self, mock_valkey):
        bot = create_bot()
        assert bot.intents.members is True

    @patch("discord_against_humanity.bot.valkey.Valkey")
    def test_valkey_attribute(self, mock_valkey):
        bot = create_bot()
        assert hasattr(bot, "valkey")
        mock_valkey.assert_called_once()

    @patch("discord_against_humanity.bot.valkey.Valkey")
    @patch.dict("os.environ", {"VALKEY_HOST": "db.example.com", "VALKEY_PORT": "6380"})
    def test_valkey_uses_env_vars(self, mock_valkey):
        create_bot()
        mock_valkey.assert_called_once_with(
            host="db.example.com", port=6380, decode_responses=True
        )

    @patch("discord_against_humanity.bot.valkey.Valkey")
    @patch.dict("os.environ", {}, clear=True)
    def test_valkey_defaults(self, mock_valkey):
        create_bot()
        mock_valkey.assert_called_once_with(
            host="localhost", port=6379, decode_responses=True
        )


class TestInitLogger:
    """Tests for init_logger()."""

    @patch("discord_against_humanity.bot.logging.config.dictConfig")
    def test_init_logger_calls_dictconfig(self, mock_dictconfig):
        init_logger()
        mock_dictconfig.assert_called_once()
