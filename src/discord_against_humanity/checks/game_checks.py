"""Custom Discord command checks for game state validation."""

import logging

from discord.ext import commands

from discord_against_humanity.domain.game import MongoGame
from discord_against_humanity.domain.player import MongoPlayer
from discord_against_humanity.utils.debug import async_log_event

logger = logging.getLogger(__name__)

__all__ = [
    "game_exists",
    "no_game_exists",
    "is_player",
    "is_not_player",
    "game_playing",
    "game_not_playing",
    "is_enough_players",
    "from_user_channel",
    "is_players_voting",
    "is_tsar_voting",
    "is_tsar",
    "is_not_tsar",
]


@async_log_event
async def game_exists(ctx: commands.Context) -> bool:
    """Check if a game exists in this guild.

    Args:
        ctx: The invocation context.

    Returns:
        True if a game exists.
    """
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)  # type: ignore[attr-defined]
    return game.document_id is not None


@async_log_event
async def no_game_exists(ctx: commands.Context) -> bool:
    """Check if no game exists in this guild.

    Args:
        ctx: The invocation context.

    Returns:
        True if no game exists.
    """
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)  # type: ignore[attr-defined]
    return game.document_id is None


@async_log_event
async def is_player(ctx: commands.Context) -> bool:
    """Check if the user is a player in the game.

    Args:
        ctx: The invocation context.

    Returns:
        True if the user is a player.
    """
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)  # type: ignore[attr-defined]
    player = await MongoPlayer.create(ctx.bot, ctx.bot.mongo, user=ctx.author)  # type: ignore[attr-defined]
    result = player.document_id in game.players_id  # type: ignore[operator]
    logger.debug("Result of is_player: %s", result)
    return result


@async_log_event
async def is_not_player(ctx: commands.Context) -> bool:
    """Check if the user is not a player in the game.

    Args:
        ctx: The invocation context.

    Returns:
        True if the user is not a player.
    """
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)  # type: ignore[attr-defined]
    player = await MongoPlayer.create(ctx.bot, ctx.bot.mongo, user=ctx.author)  # type: ignore[attr-defined]
    result = player.document_id not in game.players_id  # type: ignore[operator]
    logger.debug("Result of is_not_player: %s", result)
    return result


@async_log_event
async def game_playing(ctx: commands.Context) -> bool:
    """Check if the game is currently in progress.

    Args:
        ctx: The invocation context.

    Returns:
        True if the game is playing.
    """
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)  # type: ignore[attr-defined]
    logger.debug("Result of game_playing: %s", game.playing)
    return game.playing  # type: ignore[return-value]


@async_log_event
async def game_not_playing(ctx: commands.Context) -> bool:
    """Check if the game is not currently in progress.

    Args:
        ctx: The invocation context.

    Returns:
        True if the game is not playing.
    """
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)  # type: ignore[attr-defined]
    logger.debug("Result of game_not_playing: %s", not game.playing)
    return not game.playing


@async_log_event
async def is_enough_players(ctx: commands.Context) -> bool:
    """Check if there are enough players to start the game.

    Args:
        ctx: The invocation context.

    Returns:
        True if there are at least 2 players.
    """
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)  # type: ignore[attr-defined]
    result = len(game.players_id) >= 2  # type: ignore[arg-type]
    logger.debug("Result of is_enough_players: %s", result)
    return result


@async_log_event
async def from_user_channel(ctx: commands.Context) -> bool:
    """Check if the command was sent from the user's private channel.

    Args:
        ctx: The invocation context.

    Returns:
        True if the command was sent from the user's channel.
    """
    player = await MongoPlayer.create(ctx.bot, ctx.bot.mongo, user=ctx.author)  # type: ignore[attr-defined]
    result = ctx.channel == player.channel
    logger.debug("Result of from_user_channel: %s", result)
    return result


@async_log_event
async def is_players_voting(ctx: commands.Context) -> bool:
    """Check if it is the players' turn to vote.

    Args:
        ctx: The invocation context.

    Returns:
        True if the voting phase is for players.
    """
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)  # type: ignore[attr-defined]
    result = game.voting == "players"
    logger.debug("Result of is_players_voting: %s", result)
    return result


@async_log_event
async def is_tsar_voting(ctx: commands.Context) -> bool:
    """Check if it is the tsar's turn to vote.

    Args:
        ctx: The invocation context.

    Returns:
        True if the voting phase is for the tsar.
    """
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)  # type: ignore[attr-defined]
    result = game.voting == "tsar"
    logger.debug("Result of is_tsar_voting: %s", result)
    return result


@async_log_event
async def is_tsar(ctx: commands.Context) -> bool:
    """Check if the user is the current tsar.

    Args:
        ctx: The invocation context.

    Returns:
        True if the user is the tsar.
    """
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)  # type: ignore[attr-defined]
    player = await MongoPlayer.create(ctx.bot, ctx.bot.mongo, user=ctx.author)  # type: ignore[attr-defined]
    result = game.tsar_id == player.document_id
    logger.debug("Result of is_tsar: %s", result)
    return result


@async_log_event
async def is_not_tsar(ctx: commands.Context) -> bool:
    """Check if the user is not the current tsar.

    Args:
        ctx: The invocation context.

    Returns:
        True if the user is not the tsar.
    """
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)  # type: ignore[attr-defined]
    player = await MongoPlayer.create(ctx.bot, ctx.bot.mongo, user=ctx.author)  # type: ignore[attr-defined]
    result = game.tsar_id != player.document_id
    logger.debug("Result of is_not_tsar: %s", result)
    return result
