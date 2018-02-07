#!/bin/env python

"""Cards Against Humanity command module"""

from discord import Color
from discord.ext import commands

from cah.game import Game
from cah.player import Player
from cah.checks import *

from utils.embed import create_embed

class CardsAgainstHumanity(object):
    """Implements Cards Against Humanity commands"""

    def __init__(self, bot):
        self.bot = bot
        self.mongo_client = self.bot.mongo

    # Cards Against Humanity - Commands
    # -------------------------------------------------------------------------
    @commands.command()
    @commands.guild_only()
    async def reminder(self, ctx):
        """Displays the reminder"""
        message = self._reminder()
        await ctx.channel.send(embed=message)

    @commands.command()
    @commands.guild_only()
    @commands.check(no_game_exists)
    async def create(self, ctx):
        """Create a new game of Cards Against Humanity"""
        game = Game(ctx.bot, ctx.bot.mongo, ctx.guild)
        game.guild = ctx.guild
        game.category = await ctx.guild.create_category("Cards Against Humanity")
        game.board = await ctx.guild.create_text_channel("board", category=game.category)
        game.save()
        await ctx.message.delete()

    @commands.command()
    @commands.guild_only()
    @commands.check(game_exists)
    async def delete(self, ctx):
        """Delete a game of Cards Against Humanity"""
        game = Game(ctx.bot, ctx.bot.mongo, ctx.guild)
        for player in game.players:
            await player.channel.delete()
            player.delete()
        await game.board.delete()
        await game.category.delete()
        game.delete()
        await ctx.message.delete()

    @commands.command()
    @commands.guild_only()
    @commands.check(game_exists)
    @commands.check(is_not_player)
    async def join(self, ctx):
        """Join a Cards Against Humanity game"""
        await ctx.message.delete()
        game = Game(self.bot, self.mongo_client, ctx.guild)
        player = Player(self.bot, self.mongo_client, user=ctx.author)
        name = "_".join(ctx.author.display_name.split())
        player.guild = ctx.guild
        player.user = ctx.author
        player.channel = await ctx.guild.create_text_channel(name, category=game.category)
        player.save()
        game.add_player(player)
        game.save()
        embed = dict(description="{} has joined the game".format(ctx.author.mention))
        message = create_embed(embed)
        await game.board.send(embed=message)

    @commands.command()
    @commands.guild_only()
    @commands.check(game_exists)
    @commands.check(is_player)
    async def leave(self, ctx):
        """Leave the game"""
        await ctx.message.delete()
        game = Game(ctx.bot, ctx.bot.mongo, ctx.guild)
        player = Player(ctx.bot, ctx.bot.mongo, user=ctx.author)
        game.delete_player(player)
        if player.document_id == game.tsar.document_id:
            game.set_random_tsar()  # Set a new Tsar
        game.save()
        await player.channel.delete()
        player.delete()
        embed = dict(description="{} has leaved the game".format(ctx.author.mention))
        message = create_embed(embed)
        await game.board.send(embed=message)

    @commands.command()
    @commands.guild_only()
    @commands.check(game_exists)
    @commands.check(game_not_playing)
    @commands.check(is_enough_players)
    async def start(self, ctx, points=15):
        """Starts the game"""
        await ctx.message.delete()
        game = Game(ctx.bot, ctx.bot.mongo, ctx.guild)
        game.playing = True
        game.points = points
        game.save()
        message = self._reminder()
        await game.board.send(embed=message)
        self.bot.loop.create_task(self.run(game))

    @commands.command()
    @commands.guild_only()
    @commands.check(game_exists)
    @commands.check(game_playing)
    async def stop(self, ctx):
        game = Game(ctx.bot, ctx.bot.mongo, ctx.guild)
        game.playing = False
        game.save()

    @commands.command()
    @commands.guild_only()
    @commands.check(game_exists)
    @commands.check(is_player)
    @commands.check(game_playing)
    @commands.check(from_user_channel)
    @commands.check(is_players_voting)
    @commands.check(is_not_tsar)
    async def vote(self, ctx, *answers):
        game = Game(ctx.bot, ctx.bot.mongo, ctx.guild)
        player = Player(ctx.bot, ctx.bot.mongo, user=ctx.author)
        try:
            answers = list(map(int, answers))
            if len(answers) is not game.black_card.pick:
                embed = dict(description="You must provide {} answers. \
You provided {} answers".format(game.black_card.pick, len(answers)))
                message = create_embed(embed)
                await game.board.send(embed=message)
            elif not all(i in range(1, 8) for i in answers):
                embed = dict(description="Your answer are not between 1 and 7")
                message = create_embed(embed)
                await game.board.send(embed=message)
            else:
                player.add_answers(answers)
                embed = dict(description="{} has voted !".format(ctx.author.mention))
                message = create_embed(embed)
                await game.board.send(embed=message)
        except TypeError:
            embed = dict(description="Your answer not an integer !")
            message = create_embed(embed)
            await game.board.send(embed=message)

    @commands.command()
    @commands.guild_only()
    @commands.check(game_exists)
    @commands.check(is_player)
    @commands.check(game_playing)
    @commands.check(from_user_channel)
    @commands.check(is_tsar_voting)
    @commands.check(is_tsar)
    async def tsar(self, ctx, *, answers):
        game = Game(ctx.bot, ctx.bot.mongo, ctx.guild)
        player = Player(ctx.bot, ctx.bot.mongo, user=ctx.author)
        try:
            answers = int(answers.split(" ")[0])
            if not answers in range(1, len(game.players_id)):
               embed = dict(description="Your answer is not in the acceptable range")
               message = create_embed(embed)
               await game.board.send(embed=message)
            else:
                player.tsar_choice = answers
                player.save()
                embed = dict(description="{} has voted !".format(ctx.author.mention))
                message = create_embed(embed)
                await game.board.send(embed=message)
        except ValueError:
            embed = dict(description="Your answer is not an integer !")
            message = create_embed(embed)
            await game.board.send(embed=message)

    @commands.command()
    @commands.guild_only()
    @commands.check(game_exists)
    @commands.check(game_playing)
    async def score(self, ctx):
        game = Game(ctx.bot, ctx.bot.mongo, ctx.guild)
        await game.score()

    async def _reminder(self):
        embed = dict(name="Rules", inline=False, value="Course of the game :\n\
1. A black card (question) is picked\n\
2. Players pick white cards (answers)\n\
3. Players vote  `Use {command_prefix}vote in your channel`\n\
4. Tsar vote  `Use {command_prefix}vote in your channel`\n\
5. Deciding winner and go back to start".format(self.bot.command_prefix))
        message = create_embed(embed)
        return message

    async def run(self, game):
        """Run the game"""
        game.set_random_tsar()  # Set the Tsar
        while game.playing and all(p.score < game.points for p in game.players):
            await game.board.send("{} ! You're the tsar !".format(game.tsar.user.mention))
            game.draw_black_card()  # Draw a new Black card
            await game.send_black_card()  # Send black card to board
            for player in game.players:
                player.draw_white_cards(game.white_cards)  # Draw white cards for players
                await player.send_white_cards()  # Send white cards to dedicated channel
            await game.wait_for_players_answers()  # Wait for players to wote
            game.create_answers()
            await game.send_answers()  # Send all answers to the board
            await game.wait_for_tsar_vote()  # Wait for tsar to vote
            await game.choose_winner()  # Choose the winner
            await game.score()
        game.playing = False
        game.save()

def setup(bot):
    """Add commands to the Bot"""
    bot.add_cog(CardsAgainstHumanity(bot))
