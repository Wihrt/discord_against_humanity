#!/usr/bin/env python

from logging import info
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
    if len(game.players) >= 2:
        return True
    return False

def from_user_channel(ctx):
    player = Player(ctx.bot, ctx.bot.mongo, user=ctx.author)
    info("Command channel = " + str(ctx.channel.id) + ", Player Channel = " + str(player.channel.id))
    if ctx.channel == player.channel:
        return True
    return False

def is_players_voting(ctx):
    game = Game(ctx.bot, ctx.bot.mongo, ctx.guild)
    info("State of the game : " + game.voting)
    if game.voting == "players":
        return True
    return False

def is_tsar_voting(ctx):
    game = Game(ctx.bot, ctx.bot.mongo, ctx.guild)
    info("State of the game : " + game.voting)
    if game.voting == "tsar":
        return True
    return False

def is_tsar(ctx):
    game = Game(ctx.bot, ctx.bot.mongo, ctx.guild)
    player = Player(ctx.bot, ctx.bot.mongo, user=ctx.author)
    info("Tsar ID = " + str(game.tsar.document_id) + ", Player ID = " + str(player.document_id))
    if game.tsar.document_id == player.document_id:
        return True
    return False

def is_not_tsar(ctx):
    return not is_tsar(ctx)