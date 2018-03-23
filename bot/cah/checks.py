#!/usr/bin/env python




from logging import getLogger
from .game import MongoGame
from .player import MongoPlayer
from utils.decorator import log_event

__all__ = ["game_exists", "no_game_exists", "is_player", "is_not_player", "game_playing",
            "game_not_playing", "is_enough_players", "from_user_channel", "is_players_voting",
            "is_tsar_voting", "is_tsar", "is_not_tsar"]

LOGGER = getLogger(__name__)

@log_event
async def game_exists(ctx):
    """Checks if a game exists

    Arguments:
        ctx {Context} -- Context of the message

    Returns:
        bool -- Result
    """
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    if game.document_id is not None:
        result = True
    return result

@log_event
async def no_game_exists(ctx):
    """Checks if the game doesn't exists

    Arguments:
        ctx {Context} -- Context of the message

    Returns:
        bool -- Result
    """
    return not game_exists(ctx)

@log_event
async def is_player(ctx):
    """Checks if the Member is a Player of the game

    Arguments:
        ctx {Context} -- Context of the message

    Returns:
        bool -- Result
    """
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    player = await MongoPlayer.create(ctx.bot, ctx.bot.mongo, user=ctx.author)
    if player.document_id in game.players_id:
        result = True
    return result

@log_event
async def is_not_player(ctx):
    """Checks if the Member is not a Player of the game

    Arguments:
        ctx {Context} -- Context of the message

    Returns:
        bool -- Result
    """
    return not is_player(ctx)

@log_event
async def game_playing(ctx):
    """Checks if the game is playing

    Arguments:
        ctx {Context} -- Context of the message

    Returns:
        bool -- Result
    """
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    return game.playing

@log_event
async def game_not_playing(ctx):
    """Checks if the game is not playing

    Arguments:
        ctx {Context} -- Context of the message

    Returns:
        bool -- Result
    """
    return not game_playing(ctx)

@log_event
async def is_enough_players(ctx):
    """Checks if the game has enough player to start

    Arguments:
        ctx {Context} -- Context of the message

    Returns:
        bool -- Result
    """
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    if len(game.players_id) >= 2:
        result = True
    return result

@log_event
async def from_user_channel(ctx):
    """Checks if the message is coming from the player's channel

    Arguments:
        ctx {Context} -- Context of the message

    Returns:
        bool -- Result
    """
    result = False
    player = await MongoPlayer.create(ctx.bot, ctx.bot.mongo, user=ctx.author)
    if ctx.channel == player.channel:
        result = True
    return result

@log_event
async def is_players_voting(ctx):
    """Checks if the game let the players vote

    Arguments:
        ctx {Context} -- Context of the message

    Returns:
        bool -- Result
    """
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    if game.voting == "players":
        result = True
    return result

@log_event
async def is_tsar_voting(ctx):
    """Checks if the game let the tsar vote

    Arguments:
        ctx {Context} -- Context of the message

    Returns:
        bool -- Result
    """
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    if game.voting == "tsar":
        result = True
    return result

@log_event
async def is_tsar(ctx):
    """Checks if the player is the tsar

    Arguments:
        ctx {Context} -- Context of the message

    Returns:
        bool -- Result
    """
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    player = await MongoPlayer.create(ctx.bot, ctx.bot.mongo, user=ctx.author)
    if game.tsar_id == player.document_id:
        result = True
    return result

@log_event
async def is_not_tsar(ctx):
    """Checks if the player is not the tsar

    Arguments:
        ctx {Context} -- Context of the message

    Returns:
        bool -- Result
    """
    return not is_tsar(ctx)
