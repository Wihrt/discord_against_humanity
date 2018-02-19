#!/bin/env python

"""Cards Against Humanity command module"""

from discord import Color, PermissionOverwrite
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
        permissions = self._default_permission(ctx.guild)
        game = Game(ctx.bot, ctx.bot.mongo, ctx.guild)
        game.guild = ctx.guild
        game.category = await ctx.guild.create_category("Cards Against Humanity")
        game.board = await ctx.guild.create_text_channel("board", category=game.category, overwrites=permissions)
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
        permissions = self._default_permission(ctx.guild)
        user_permissions = PermissionOverwrite(read_messages=True, send_messages=True)
        game = Game(self.bot, self.mongo_client, ctx.guild)
        player = Player(self.bot, self.mongo_client, user=ctx.author)
        name = "_".join(ctx.author.display_name.split())
        player.guild = ctx.guild
        player.user = ctx.author
        player.channel = await ctx.guild.create_text_channel(name, category=game.category, overwrites=permissions)
        await game.board.set_permissions(ctx.author, overwrite=user_permissions)
        await player.channel.set_permissions(ctx.author, overwrite=user_permissions)
        player.save()
        game.add_player(player)
        game.save()
        await game.board.send("{} has joined the game !".format(ctx.author.mention))

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
        await game.board.send("{} has leaved the game !".format(ctx.author.mention))
        await game.board.set_permissions(ctx.author, overwrite=None)

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
        await game.board.send("The game will start !")
        message = self._reminder()
        await game.board.send(embed=message)

        game.set_random_tsar()  # Set the Tsar
        while game.playing and all(p.score < game.points for p in game.players):
            await game.board.send("{} ! You're the tsar !".format(game.tsar.user.mention))
            await game.draw_black_card()  # Send black card to board
            for player in game.players:
                await player.draw_white_cards(game.white_cards)  # Draw white cards for players
            await game.wait_for_players_answers()  # Wait for players to wote
            await game.send_answers()  # Send all answers to the board
            await game.wait_for_tsar_vote()  # Wait for tsar to vote
            await game.choose_winner()  # Choose the winner
            await game.score()
        game.playing = False
        game.save()


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
                await player.channel.send("You must provide {} answers. \
You provided {} answers".format(game.black_card.pick, len(answers)))
            elif not all(i in range(1, 8) for i in answers):
                await player.channel.send("Your answer(s) are not between 1 and 7")
            else:
                player.add_answers(answers)
                await game.board.send("{} has voted !".format(ctx.author.mention))
        except TypeError:
            await player.channel.send("Your answer is not an integer !")

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
                await player.channel.send("Your answer is not in the acceptable range")
            else:
                player.tsar_choice = answers
                player.save()
                await game.board.send("{} has voted !".format(ctx.author.mention))
        except ValueError:
            await player.channel.send("Your answer is not an integer !")

    @commands.command()
    @commands.guild_only()
    @commands.check(game_exists)
    @commands.check(game_playing)
    async def score(self, ctx):
        game = Game(ctx.bot, ctx.bot.mongo, ctx.guild)
        await game.score()

    def _reminder(self):
        embed = dict(fields=dict(name="Reminder", inline=False, value="Course of the game :\n\
1. A black card (question) is picked\n\
2. Players pick white cards (answers)\n\
3. Players vote  `Use {0}vote in your channel`\n\
4. Tsar vote  `Use {0}tsar in your channel`\n\
5. Deciding winner and go back to start".format(self.bot.command_prefix)))
        message = create_embed(embed)
        return message

    def _default_permission(self, guild):
        permissions = dict()
        permissions[guild.default_role] = PermissionOverwrite(read_messages=False)  # Nobody can read the channel
        permissions[guild.me] = PermissionOverwrite(read_messages=True, send_messages=True)  # For the bot
        return permissions

    # async def run(self, game):
    #     """Run the game"""
    #     game.set_random_tsar()  # Set the Tsar
    #     while game.playing and all(p.score < game.points for p in game.players):
    #         await game.board.send("{} ! You're the tsar !".format(game.tsar.user.mention))
    #         await game.send_black_card()  # Send black card to board
    #         for player in game.players:
    #             player.draw_white_cards(game.white_cards)  # Draw white cards for players
    #             await player.send_white_cards()  # Send white cards to dedicated channel
    #         await game.wait_for_players_answers()  # Wait for players to wote
    #         await game.send_answers()  # Send all answers to the board
    #         await game.wait_for_tsar_vote()  # Wait for tsar to vote
    #         await game.choose_winner()  # Choose the winner
    #         await game.score()
    #     game.playing = False
    #     game.save()

def setup(bot):
    """Add commands to the Bot"""
    bot.add_cog(CardsAgainstHumanity(bot))
