"""Tests for bot creation and configuration."""

from unittest.mock import patch

from discord import Intents
from discord.ext.commands import Bot

from discord_against_humanity.bot import create_bot, init_logger


class TestCreateBot:
    """Tests for create_bot()."""

    @patch("discord_against_humanity.bot.AsyncIOMotorClient")
    def test_returns_bot_instance(self, mock_motor):
        bot = create_bot()
        assert isinstance(bot, Bot)

    @patch("discord_against_humanity.bot.AsyncIOMotorClient")
    def test_command_prefix(self, mock_motor):
        bot = create_bot()
        assert bot.command_prefix == "!"

    @patch("discord_against_humanity.bot.AsyncIOMotorClient")
    def test_intents_message_content(self, mock_motor):
        bot = create_bot()
        assert bot.intents.message_content is True

    @patch("discord_against_humanity.bot.AsyncIOMotorClient")
    def test_intents_members(self, mock_motor):
        bot = create_bot()
        assert bot.intents.members is True

    @patch("discord_against_humanity.bot.AsyncIOMotorClient")
    def test_mongo_attribute(self, mock_motor):
        bot = create_bot()
        assert hasattr(bot, "mongo")
        mock_motor.assert_called_once()

    @patch("discord_against_humanity.bot.AsyncIOMotorClient")
    @patch.dict("os.environ", {"MONGO_HOST": "db.example.com", "MONGO_PORT": "27018"})
    def test_mongo_uses_env_vars(self, mock_motor):
        create_bot()
        mock_motor.assert_called_once_with(host="db.example.com", port=27018)

    @patch("discord_against_humanity.bot.AsyncIOMotorClient")
    @patch.dict("os.environ", {}, clear=True)
    def test_mongo_defaults(self, mock_motor):
        create_bot()
        mock_motor.assert_called_once_with(host="localhost", port=27017)


class TestInitLogger:
    """Tests for init_logger()."""

    @patch("discord_against_humanity.bot.logging.config.dictConfig")
    def test_init_logger_calls_dictconfig(self, mock_dictconfig):
        init_logger()
        mock_dictconfig.assert_called_once()
