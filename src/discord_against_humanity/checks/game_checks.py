"""Custom Discord command checks for game state validation."""

import logging

import discord

from discord_against_humanity.domain.game import Game
from discord_against_humanity.domain.player import Player
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
async def game_exists(interaction: discord.Interaction) -> bool:
    """Check if a game exists in this guild.

    Args:
        interaction: The Discord interaction.

    Returns:
        True if a game exists.
    """
    assert interaction.guild is not None
    game = await Game.create(
        interaction.client, interaction.client.valkey, interaction.guild  # type: ignore[attr-defined]
    )
    return game.document_id is not None


@async_log_event
async def no_game_exists(interaction: discord.Interaction) -> bool:
    """Check if no game exists in this guild.

    Args:
        interaction: The Discord interaction.

    Returns:
        True if no game exists.
    """
    assert interaction.guild is not None
    game = await Game.create(
        interaction.client, interaction.client.valkey, interaction.guild  # type: ignore[attr-defined]
    )
    return game.document_id is None


@async_log_event
async def is_player(interaction: discord.Interaction) -> bool:
    """Check if the user is a player in the game.

    Args:
        interaction: The Discord interaction.

    Returns:
        True if the user is a player.
    """
    assert interaction.guild is not None
    game = await Game.create(
        interaction.client, interaction.client.valkey, interaction.guild  # type: ignore[attr-defined]
    )
    player = await Player.create(
        interaction.client,
        interaction.client.valkey,  # type: ignore[attr-defined]
        user=interaction.user,
        guild=interaction.guild,
    )
    result = player.document_id in game.players_id  # type: ignore[operator]
    logger.debug("Result of is_player: %s", result)
    return result


@async_log_event
async def is_not_player(interaction: discord.Interaction) -> bool:
    """Check if the user is not a player in the game.

    Args:
        interaction: The Discord interaction.

    Returns:
        True if the user is not a player.
    """
    assert interaction.guild is not None
    game = await Game.create(
        interaction.client, interaction.client.valkey, interaction.guild  # type: ignore[attr-defined]
    )
    player = await Player.create(
        interaction.client,
        interaction.client.valkey,  # type: ignore[attr-defined]
        user=interaction.user,
        guild=interaction.guild,
    )
    result = player.document_id not in game.players_id  # type: ignore[operator]
    logger.debug("Result of is_not_player: %s", result)
    return result


@async_log_event
async def game_playing(interaction: discord.Interaction) -> bool:
    """Check if the game is currently in progress.

    Args:
        interaction: The Discord interaction.

    Returns:
        True if the game is playing.
    """
    assert interaction.guild is not None
    game = await Game.create(
        interaction.client, interaction.client.valkey, interaction.guild  # type: ignore[attr-defined]
    )
    logger.debug("Result of game_playing: %s", game.playing)
    return game.playing  # type: ignore[return-value]


@async_log_event
async def game_not_playing(interaction: discord.Interaction) -> bool:
    """Check if the game is not currently in progress.

    Args:
        interaction: The Discord interaction.

    Returns:
        True if the game is not playing.
    """
    assert interaction.guild is not None
    game = await Game.create(
        interaction.client, interaction.client.valkey, interaction.guild  # type: ignore[attr-defined]
    )
    logger.debug("Result of game_not_playing: %s", not game.playing)
    return not game.playing


@async_log_event
async def is_enough_players(interaction: discord.Interaction) -> bool:
    """Check if there are enough players to start the game.

    Args:
        interaction: The Discord interaction.

    Returns:
        True if there are at least 2 players.
    """
    assert interaction.guild is not None
    game = await Game.create(
        interaction.client, interaction.client.valkey, interaction.guild  # type: ignore[attr-defined]
    )
    result = len(game.players_id) >= 2  # type: ignore[arg-type]
    logger.debug("Result of is_enough_players: %s", result)
    return result


@async_log_event
async def from_user_channel(interaction: discord.Interaction) -> bool:
    """Check if the command was sent from the user's private channel.

    Args:
        interaction: The Discord interaction.

    Returns:
        True if the command was sent from the user's channel.
    """
    assert interaction.guild is not None
    player = await Player.create(
        interaction.client,
        interaction.client.valkey,  # type: ignore[attr-defined]
        user=interaction.user,
        guild=interaction.guild,
    )
    result = interaction.channel == player.channel
    logger.debug("Result of from_user_channel: %s", result)
    return result


@async_log_event
async def is_players_voting(interaction: discord.Interaction) -> bool:
    """Check if it is the players' turn to vote.

    Args:
        interaction: The Discord interaction.

    Returns:
        True if the voting phase is for players.
    """
    assert interaction.guild is not None
    game = await Game.create(
        interaction.client, interaction.client.valkey, interaction.guild  # type: ignore[attr-defined]
    )
    result = game.voting == "players"
    logger.debug("Result of is_players_voting: %s", result)
    return result


@async_log_event
async def is_tsar_voting(interaction: discord.Interaction) -> bool:
    """Check if it is the tsar's turn to vote.

    Args:
        interaction: The Discord interaction.

    Returns:
        True if the voting phase is for the tsar.
    """
    assert interaction.guild is not None
    game = await Game.create(
        interaction.client, interaction.client.valkey, interaction.guild  # type: ignore[attr-defined]
    )
    result = game.voting == "tsar"
    logger.debug("Result of is_tsar_voting: %s", result)
    return result


@async_log_event
async def is_tsar(interaction: discord.Interaction) -> bool:
    """Check if the user is the current tsar.

    Args:
        interaction: The Discord interaction.

    Returns:
        True if the user is the tsar.
    """
    assert interaction.guild is not None
    game = await Game.create(
        interaction.client, interaction.client.valkey, interaction.guild  # type: ignore[attr-defined]
    )
    player = await Player.create(
        interaction.client,
        interaction.client.valkey,  # type: ignore[attr-defined]
        user=interaction.user,
        guild=interaction.guild,
    )
    result = game.tsar_id == player.document_id
    logger.debug("Result of is_tsar: %s", result)
    return result


@async_log_event
async def is_not_tsar(interaction: discord.Interaction) -> bool:
    """Check if the user is not the current tsar.

    Args:
        interaction: The Discord interaction.

    Returns:
        True if the user is not the tsar.
    """
    assert interaction.guild is not None
    game = await Game.create(
        interaction.client, interaction.client.valkey, interaction.guild  # type: ignore[attr-defined]
    )
    player = await Player.create(
        interaction.client,
        interaction.client.valkey,  # type: ignore[attr-defined]
        user=interaction.user,
        guild=interaction.guild,
    )
    result = game.tsar_id != player.document_id
    logger.debug("Result of is_not_tsar: %s", result)
    return result
