#!/usr/bin/env python

from .game import Game
from .player import Player

def game_exists(ctx):
    game = Game(ctx.bot, ctx.bot.mongo, ctx.guild)
    if not game.document_id is None:
        return True
    return False

def no_game_exists(ctx):
    return not game_exists(ctx)

def is_player(ctx):
    game = Game(ctx.bot, ctx.bot.mongo, ctx.guild)
    player = Player(ctx.bot, ctx.bot.mongo, user=ctx.author)
    if player.document_id in game.players_id:
        return True
    return False

def is_not_player(ctx):
    return not is_player(ctx)

def game_playing(ctx):
    game = Game(ctx.bot, ctx.bot.mongo, ctx.guild)
    return game.playing

def game_not_playing(ctx):
    return not game_playing(ctx)

def is_enough_players(ctx):
    game = Game(ctx.bot, ctx.bot.mongo, ctx.guild)
    if len(game.players) >= 3:
        return True
    return False

def from_user_channel(ctx):
    player = Player(ctx.bot, ctx.bot.mongo, user=ctx.author)
    if ctx.channel == player.channel:
        return True
    return False

def is_players_voting(ctx):
    game = Game(ctx.bot, ctx.bot.mongo, ctx.guild)
    if game.voting is "players":
        return True

def is_tsar_voting(ctx):
    game = Game(ctx.bot, ctx.bot.mongo, ctx.guild)
    if game.voting is "tsar":
        return True

def is_tsar(ctx):
    game = Game(ctx.bot, ctx.bot.mongo, ctx.guild)
    player = Player(ctx.bot, ctx.bot.mongo, user=ctx.author)
    if game.tsar.document_id == player.document_id:
        return True

def is_not_tsar(ctx):
    return not is_tsar(ctx)