#!/usr/bin/env python

from logging import getLogger
from .game import MongoGame
from .player import MongoPlayer
from utils.debug import async_log_event

__all__ = ["game_exists", "no_game_exists", "is_player", "is_not_player", "game_playing",
           "game_not_playing", "is_enough_players", "from_user_channel", "is_players_voting",
           "is_tsar_voting", "is_tsar", "is_not_tsar"]

LOGGER = getLogger(__name__)

@async_log_event
async def game_exists(ctx):
    """Check if game exists"""
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    if game.document_id is not None:
        result = True
    return result

@async_log_event
async def no_game_exists(ctx):
    """Check if game does not exists"""
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    if game.document_id is None:
        result = True
    return result

@async_log_event
async def is_player(ctx):
    """Checks if user is a player of the game"""
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    player = await MongoPlayer.create(ctx.bot, ctx.bot.mongo, user=ctx.author)
    if player.document_id in game.players_id:
        result = True
    LOGGER.debug("Result of is_player : %s" % result)
    return result

@async_log_event
async def is_not_player(ctx):
    """Check if user is not a player of the game"""
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    player = await MongoPlayer.create(ctx.bot, ctx.bot.mongo, user=ctx.author)
    if player.document_id not in game.players_id:
        result = True
    LOGGER.debug("Result of is_not_player : %s" % result)
    return result

@async_log_event
async def game_playing(ctx):
    """Checks if the game is playing"""
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    LOGGER.debug("Result of game_playing : %s" % game.playing)
    return game.playing

@async_log_event
async def game_not_playing(ctx):
    """Checks if the game is not playing"""
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    LOGGER.debug("Result of game_not playing : %s" % (not game.playing))
    return not game.playing

@async_log_event
async def is_enough_players(ctx):
    """Checks if there is enough players to start the game"""
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    if len(game.players_id) >= 2:
        result = True
    LOGGER.debug("Result of is_enough_players : %s" % result)
    return result

@async_log_event
async def from_user_channel(ctx):
    """Checks if the command is sent from user channel"""
    result = False
    player = await MongoPlayer.create(ctx.bot, ctx.bot.mongo, user=ctx.author)
    if ctx.channel == player.channel:
        result = True
    LOGGER.debug("Result of from_user_channel : %s" % result)
    return result

@async_log_event
async def is_players_voting(ctx):
    """Checks if the players can vote"""
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    if game.voting == "players":
        result = True
    LOGGER.debug("Result of is_players_voting : %s" % result)
    return result

@async_log_event
async def is_tsar_voting(ctx):
    """Checks if the tsar can vote"""
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    if game.voting == "tsar":
        result = True
    LOGGER.debug("Result of is_tsar_voting: %s" % result)
    return result

@async_log_event
async def is_tsar(ctx):
    """Checks if the player is the tsar"""
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    player = await MongoPlayer.create(ctx.bot, ctx.bot.mongo, user=ctx.author)
    if game.tsar_id == player.document_id:
        result = True
    LOGGER.debug("Result of is_tsar: %s" % result)
    return result

@async_log_event
async def is_not_tsar(ctx):
    """Checks if the player is not the tsar"""
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    player = await MongoPlayer.create(ctx.bot, ctx.bot.mongo, user=ctx.author)
    if game.tsar_id != player.document_id:
        result = True
    LOGGER.debug("Result of is_not_tsar: %s" % result)
    return result
