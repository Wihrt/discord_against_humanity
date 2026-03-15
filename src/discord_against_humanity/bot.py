"""Bot setup and event handlers for Discord Against Humanity."""

import json
import logging
import logging.config
from importlib import resources
from os import environ
from traceback import print_tb
from typing import Any

import discord
import valkey.asyncio as valkey
from discord import Color, app_commands
from discord.ext.commands import Bot

from discord_against_humanity.utils.embed import create_embed

logger = logging.getLogger("discord_against_humanity.bot")

EXTENSIONS = ["discord_against_humanity.commands.cah"]


def init_logger() -> None:
    """Initialize logging from the packaged logging configuration."""
    config_path = resources.files("discord_against_humanity") / "logging_config.json"
    with resources.as_file(config_path) as path:
        with open(path) as config_file:
            data = json.load(config_file)
            logging.config.dictConfig(data)


def create_bot() -> Bot:
    """Create and configure the Discord bot instance.

    Returns:
        The configured Bot instance.
    """
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    bot = Bot(command_prefix="!", intents=intents)
    bot.valkey = valkey.Valkey(  # type: ignore[attr-defined]
        host=environ.get("VALKEY_HOST", "localhost"),
        port=int(environ.get("VALKEY_PORT", "6379")),
        decode_responses=True,
    )

    @bot.event
    async def on_ready() -> None:
        """Log bot startup information."""
        logging.info("Logged in as:")
        logging.info("Username: %s", bot.user.name if bot.user else "Unknown")
        logging.info("ID: %s", bot.user.id if bot.user else "Unknown")
        logging.info("------")

    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        """Handle slash command errors by sending an ephemeral message.

        Args:
            interaction: The interaction that triggered the error.
            error: The error that was raised.
        """
        content: dict[str, Any] = {"colour": Color.dark_red()}
        logger.critical("%s %s", interaction.command, error)
        field: dict[str, Any] = {"name": "Error", "inline": False}

        if isinstance(error, app_commands.CheckFailure):
            field["value"] = ":no_entry_sign: A precondition check has failed."
        elif isinstance(error, app_commands.CommandOnCooldown):
            field["value"] = (
                f":stopwatch: This command is on cooldown, "
                f"retry after {error.retry_after:.2f} seconds"
            )
        elif isinstance(error, app_commands.MissingPermissions):
            field["value"] = f":no_entry_sign: {error}"
        elif isinstance(error, app_commands.CommandInvokeError):
            cmd_name = (
                interaction.command.name if interaction.command else "unknown"
            )
            field["value"] = (
                f":stop_sign: The command {cmd_name} has thrown an error."
            )
            logger.critical("In %s:", cmd_name)
            print_tb(error.original.__traceback__)
            logger.critical(
                "%s: %s", type(error.original).__name__, error.original
            )
        else:
            field["value"] = ":x: An unexpected error occurred."

        content["fields"] = field
        message = create_embed(content)

        if interaction.response.is_done():
            await interaction.followup.send(embed=message, ephemeral=True)
        else:
            await interaction.response.send_message(
                embed=message, ephemeral=True
            )

    return bot


async def load_extensions(bot: Bot) -> None:
    """Load all bot extensions.

    Args:
        bot: The bot instance to load extensions into.
    """
    for extension in EXTENSIONS:
        try:
            await bot.load_extension(extension)
        except Exception as err:
            exc = f"{type(err).__name__}: {err}"
            logger.critical("Failed to load extension %s\n%s", extension, exc)


def main() -> None:
    """Run the Discord Against Humanity bot."""
    init_logger()
    bot = create_bot()

    @bot.event
    async def setup_hook() -> None:
        """Load extensions and sync slash commands when the bot starts."""
        await load_extensions(bot)
        await bot.tree.sync()

    token = environ.get("DISCORD_TOKEN", "")
    if not token:
        logger.critical("DISCORD_TOKEN environment variable is not set")
        return
    bot.run(token)


if __name__ == "__main__":
    main()
