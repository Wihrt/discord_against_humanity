"""Bot setup and event handlers for Discord Against Humanity."""

import json
import logging
import logging.config
from importlib import resources
from os import environ
from traceback import print_tb

import discord
from discord import Color
from discord.ext.commands import Bot, errors
from motor.motor_asyncio import AsyncIOMotorClient

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

    bot = Bot(command_prefix="$", intents=intents)
    bot.mongo = AsyncIOMotorClient(  # type: ignore[attr-defined]
        host=environ.get("MONGO_HOST", "localhost"),
        port=int(environ.get("MONGO_PORT", "27017")),
    )

    @bot.event
    async def on_ready() -> None:
        """Log bot startup information."""
        logging.info("Logged in as:")
        logging.info("Username: %s", bot.user.name if bot.user else "Unknown")
        logging.info("ID: %s", bot.user.id if bot.user else "Unknown")
        logging.info("------")

    @bot.event
    async def on_command(ctx: discord.ext.commands.Context) -> None:  # type: ignore[name-defined]
        """Log command invocations.

        Args:
            ctx: The invocation context.
        """
        logger.debug("Command %s called. Arguments: %s", ctx.command, ctx.args)

    @bot.event
    async def on_command_error(
        ctx: discord.ext.commands.Context,  # type: ignore[name-defined]
        error: errors.CommandError,
    ) -> None:
        """Handle command errors by sending a DM to the invoking user.

        Args:
            ctx: The invocation context.
            error: The error that was raised.
        """
        content: dict = {"colour": Color.dark_red()}
        logging.critical("%s %s", ctx.command, error)
        field: dict = {"name": "Error", "inline": False}

        if isinstance(error, errors.NoPrivateMessage):
            field["value"] = (
                ":warning: This command cannot be used in private messages."
            )
        elif isinstance(error, errors.CommandOnCooldown):
            field["value"] = (
                f":stopwatch: This command is on cooldown, "
                f"retry after {error.retry_after:.2f} seconds"
            )
        elif isinstance(error, errors.DisabledCommand):
            field["value"] = "This command is disabled and cannot be used."
        elif isinstance(error, errors.CommandNotFound):
            field["value"] = (
                f":grey_question: Unknown command. "
                f"Use `{ctx.prefix}help` to get commands"
            )
        elif isinstance(error, errors.MissingPermissions):
            field["value"] = f":no_entry_sign: {error}"
        elif isinstance(error, errors.MissingRequiredArgument):
            field["value"] = "An argument is missing"
        elif isinstance(error, errors.CheckFailure):
            field["value"] = ":no_entry_sign: At least 1 check has failed"
        elif isinstance(error, errors.NotOwner):
            field["value"] = ":no_entry_sign: You are not the owner of the bot"
        elif isinstance(error, errors.CommandInvokeError):
            field["value"] = (
                f":stop_sign: The command {ctx.command} has thrown an error."
            )
            cmd_name = ctx.command.qualified_name if ctx.command else "unknown"
            logging.critical("In %s:", cmd_name)
            print_tb(error.original.__traceback__)
            logging.critical("%s: %s", type(error.original).__name__, error.original)

        content["fields"] = field
        message = create_embed(content)
        await ctx.author.send(embed=message)

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
        """Load extensions when the bot starts."""
        await load_extensions(bot)

    token = environ.get("DISCORD_TOKEN", "")
    if not token:
        logger.critical("DISCORD_TOKEN environment variable is not set")
        return
    bot.run(token)


if __name__ == "__main__":
    main()
