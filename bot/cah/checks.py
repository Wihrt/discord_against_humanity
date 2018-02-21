#!/usr/bin/env python

from logging import info
from .game import MongoGame
from .player import MongoPlayer

async def game_exists(ctx):
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    if game.document_id is not None:
        result = True
    return result

async def no_game_exists(ctx):
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    if game.document_id is None:
        result = True
    return result

async def is_player(ctx):
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    player = await MongoPlayer.create(ctx.bot, ctx.bot.mongo, user=ctx.author)
    if player.document_id in game.players_id:
        result = True
    return result

async def is_not_player(ctx):
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    player = await MongoPlayer.create(ctx.bot, ctx.bot.mongo, user=ctx.author)
    if player.document_id not in game.players_id:
        result = True
    return result

async def game_playing(ctx):
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    return game.playing

async def game_not_playing(ctx):
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    return not game.playing

async def is_enough_players(ctx):
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    if len(game.players_id) >= 2:
        result = True
    return result

async def from_user_channel(ctx):
    result = False
    player = await MongoPlayer.create(ctx.bot, ctx.bot.mongo, user=ctx.author)
    if ctx.channel == player.channel:
        result = True
    return result

async def is_players_voting(ctx):
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    if game.voting == "players":
        result = True
    return result

async def is_tsar_voting(ctx):
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    if game.voting == "tsar":
        result = True
    return result

async def is_tsar(ctx):
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    player = await MongoPlayer.create(ctx.bot, ctx.bot.mongo, user=ctx.author)
    if game.tsar_id == player.document_id:
        result = True
    return result

async def is_not_tsar(ctx):
    result = False
    game = await MongoGame.create(ctx.bot, ctx.bot.mongo, ctx.guild)
    player = await MongoPlayer.create(ctx.bot, ctx.bot.mongo, user=ctx.author)
    if game.tsar_id != player.document_id:
        result = True
    return result
