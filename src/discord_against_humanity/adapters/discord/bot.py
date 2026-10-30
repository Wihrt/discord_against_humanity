"""Discord client wiring and error reporting."""

import logging
from collections.abc import Callable

import discord
from discord import app_commands
from discord.ext import commands

from discord_against_humanity.adapters.discord.cog import CardsAgainstHumanity
from discord_against_humanity.adapters.discord.notifier import DiscordNotifier
from discord_against_humanity.adapters.discord.views import DYNAMIC_ITEMS
from discord_against_humanity.application.ports import GameNotifier
from discord_against_humanity.application.service import GameService
from discord_against_humanity.domain.errors import DomainError

logger = logging.getLogger(__name__)


def error_message(error: app_commands.AppCommandError) -> str:
    """Turn a command error into the text shown to the user."""
    original = error.original if isinstance(error, app_commands.CommandInvokeError) else error
    if isinstance(original, DomainError):
        return f":no_entry_sign: {original}"
    if isinstance(original, app_commands.NoPrivateMessage):
        return ":no_entry_sign: This command only works in a server."
    if isinstance(original, app_commands.CommandOnCooldown):
        return f":stopwatch: Slow down! Retry in {original.retry_after:.0f}s."
    if isinstance(original, app_commands.BotMissingPermissions):
        missing = ", ".join(original.missing_permissions)
        return f":no_entry_sign: I am missing permissions: {missing}."
    if isinstance(original, discord.Forbidden):
        return ":no_entry_sign: I am not allowed to do that. Check my permissions."
    return ":x: Something went wrong, please try again."


async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    """Report every failed command to its author, privately."""
    original = getattr(error, "original", error)
    if isinstance(original, DomainError):
        logger.debug("Rule violation in /%s: %s", interaction.command, original)
    else:
        logger.error("Error in /%s", interaction.command, exc_info=original)

    content = error_message(error)
    if interaction.response.is_done():
        await interaction.followup.send(content, ephemeral=True)
    else:
        await interaction.response.send_message(content, ephemeral=True)


class CardsBot(commands.Bot):
    """The bot only uses slash commands and needs no privileged intent."""

    def __init__(self, build_service: Callable[[GameNotifier], GameService]) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=discord.Intents.default(),
            allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
        )
        self.service = build_service(DiscordNotifier(self))
        self.tree.error(on_app_command_error)

    async def setup_hook(self) -> None:
        await self.add_cog(CardsAgainstHumanity(self.service))
        # Buttons are routed by custom ID, so they survive restarts.
        self.add_dynamic_items(*DYNAMIC_ITEMS)
        synced = await self.tree.sync()
        logger.info("Synced %d slash commands", len(synced))

    async def on_ready(self) -> None:
        user = self.user
        logger.info("Logged in as %s (%s)", user, user.id if user else "?")
