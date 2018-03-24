#!/bin/env python

"""Itoxx Discord Bot"""

# Imports
from logging.config import dictConfig
from logging import getLogger, Formatter, FileHandler, StreamHandler, info, critical, INFO
from os import environ
from sys import stdout
from traceback import print_tb
from json import load

from discord import Color
from discord.ext.commands import errors
from discord.ext.commands.bot import Bot
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient

from utils.embed import create_embed

BOT = Bot(command_prefix="$", pm_help=False)  # Create the bot
BOT.mongo = AsyncIOMotorClient(host=environ["MONGO_HOST"], port=int(environ["MONGO_PORT"]),
                               connect=True)

# Extensions to load at start
LOGGER = getLogger("discord_against_humanity.bot")
EXTENSIONS = ["commands.discord_against_humanity"]


def init_logger():
    """Set the logger to the desired level

    Keyword Arguments:
        level {int} -- Level of logging (default: {INFO})
    """
    with open("logging.json", "r") as config_file:
        data = load(config_file)
        dictConfig(data)

@BOT.event
async def on_ready():
    """Triggered when the bot starts

    Decorators:
        BOT.event
    """
    info('Logged in as:')
    info('Username: {}'.format(BOT.user.name))
    info('ID: {}'.format(str(BOT.user.id)))
    info('------')

@BOT.event
async def on_command(ctx):
    """Triggered when a command is called

    Arguments:
        ctx {[type]} -- [description]
    """
    LOGGER.debug("Command %s called. Arguments : %s" %(ctx.command, ctx.args))

@BOT.event
async def on_command_error(ctx, error):
    """Triggered when a command send an error

    Decorators:
        BOT.event

    Arguments:
        ctx {Context} -- Context of the message
        error {Exception} -- Discord error
    """
    content = dict(colour=Color.dark_red())
    critical(ctx.command, error)
    field = dict(name="Error", inline=False)
    if isinstance(error, errors.NoPrivateMessage):
        field["value"] = ":warning: This command cannot be used in private messages."
    elif isinstance(error, errors.CommandOnCooldown):
        field["value"] = ":stopwatch: This command is on cooldown, \
retry after {:.2f} seconds".format(error.retry_after)
    elif isinstance(error, errors.DisabledCommand):
        field["value"] = "This command is disabled and cannot be used."
    elif isinstance(error, errors.CommandNotFound):
        field["value"] = ":grey_question: Unknown command. \
Use `{}help` to get commands".format(ctx.prefix)
    elif isinstance(error, errors.MissingPermissions):
        field["value"] = ":no_entry_sign: {}".format(error.message)
    elif isinstance(error, errors.MissingRequiredArgument):
        field["value"] = "An argument is missing"
    elif isinstance(error, errors.CheckFailure):
        field["value"] = ":no_entry_sign: At least 1 check has failed"
    elif isinstance(error, errors.NotOwner):
        field["value"] = ":no_entry_sign: You are not the owner of the bot"
    elif isinstance(error, errors.CommandInvokeError):
        field["value"] = ":stop_sign: The command {} has thrown an error.".format(ctx.command)
        critical('In {0.command.qualified_name}:'.format(ctx))
        print_tb(error.original.__traceback__)
        critical('{0.__class__.__name__}: {0}'.format(error.original))
    content["fields"] = field
    message = create_embed(content)
    await ctx.author.send(embed=message)

def main():
    init_logger()
    for extension in EXTENSIONS:
        try:
            BOT.load_extension(extension)
        except ImportError as err:
            exc = '{}: {}'.format(type(err).__name__, err)
            LOGGER.critical('Failed to load extension {}\n{}'.format(extension, exc))
    with open("token.txt", "r") as token_file:
        TOKEN = token_file.read()
        BOT.run(TOKEN)

if __name__ == '__main__':
    main()
