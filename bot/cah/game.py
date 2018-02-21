#!/usr/bin/env python

"""Card Against Humanity's game class"""

from logging import info
from asyncio import sleep
from random import sample, shuffle
from discord import CategoryChannel, Guild, TextChannel

from utils.embed import create_embed
from utils.mongodoc import MongoDocument
from .player import MongoPlayer
from .cards import MongoBlackCard


class MongoGame(MongoDocument):
    """Class for Game Mongo Document"""

    _DATABASE = "cards_against_humanity"
    _COLLECTION = "games"

    # Properties
    # ---------------------------------------------------------------------------------------------
    @property
    def guild(self):
        """Get Guild

        Returns:
            Guild -- Game's guild
        """
        try:
            return self._bot.get_guild(self._document["guild"])
        except KeyError:
            return None

    @guild.setter
    def guild(self, value):
        """Set guild

        Arguments:
            value {Guild} -- Game's guild

        Raises:
            TypeError -- Wrong type
        """
        if not isinstance(value, Guild):
            raise TypeError("Wrong type for value : %s" % type(value))
        self._document["guild"] = value.id

    @property
    def category(self):
        """Get Category channel

        Returns:
            CategoryChannel -- Game's category channel
        """
        try:
            return self.guild.get_channel(self._document["category"])
        except (AttributeError, KeyError):
            return None

    @category.setter
    def category(self, value):
        """Set Category channel

        Arguments:
            value {CategoryChannel} -- Game's category channel

        Raises:
            TypeError -- Wrong type
        """
        if not isinstance(value, CategoryChannel):
            raise TypeError("Wrong type for value : %s" % type(value))
        self._document["category"] = value.id

    @property
    def board(self):
        """Get Board channel

        Returns:
            TextChannel -- Game's board channel
        """
        try:
            return self.guild.get_channel(self._document["board"])
        except (AttributeError, KeyError):
            return None

    @board.setter
    def board(self, value):
        """Set Board channel

        Arguments:
            value {TextChannel} -- Game's board channel

        Raises:
            TypeError -- Wrong type
        """
        if not isinstance(value, TextChannel):
            raise TypeError("Wrong type for value : %s" % type(value))
        self._document["board"] = value.id

    @property
    def points(self):
        """Get max number of points

        Returns:
            int -- Max number of points
        """
        try:
            return self._document["points"]
        except KeyError:
            return None

    @points.setter
    def points(self, value):
        """Set max number of points

        Arguments:
            value {int} -- Max number of points

        Raises:
            TypeError -- Wrong type
        """
        if not isinstance(value, int):
            raise TypeError("Wrong type for value : %s" % type(value))
        self._document["points"] = value

    @property
    def playing(self):
        """Get the game's status

        Returns:
            bool -- Game's status
        """
        try:
            return self._document["playing"]
        except KeyError:
            return None

    @playing.setter
    def playing(self, value):
        """Set the game status

        Arguments:
            value {bool} -- Game's playing

        Raises:
            TypeError -- Wrong type
        """
        if not isinstance(value, bool):
            raise TypeError("Wrong type for value : %s" % type(value))
        self._document["playing"] = value

    @property
    def voting(self):
        """Get the game's voting status

        Returns:
            str - Which players must vote
        """
        try:
            return self._document["voting"]
        except KeyError:
            return None

    @voting.setter
    def voting(self, value):
        """Set the game's voting status

        Arguments:
            value {bool} -- Game's voting status

        Raises:
            TypeError -- Wrong type
            ValueError -- Wrong value
        """
        if not isinstance(value, str):
            raise TypeError("Wrong type for value : %s" % type(value))
        elif not value in ["players", "tsar", "nobody"]:
            raise ValueError("Wrong value for voting")
        else:
            self._document["voting"] = value

    @property
    def players_id(self):
        """Get the player's ObjectId

        Returns:
            *ObjectId -- List of ObjectId
        """
        try:
            return self._document["players"]
        except KeyError:
            return None

    @property
    def black_cards_id(self):
        """Get the Black Card's Object ID

        Returns:
            *ObjectId -- List of ObjectId
        """
        try:
            return self._document["black_cards"]
        except KeyError:
            return None

    @property
    def white_cards_id(self):
        """Get the White Card's Object ID

        Returns:
            *ObjectId -- List of ObjectId
        """
        try:
            return self._document["white_cards"]
        except KeyError:
            return None

    @property
    def tsar_id(self):
        """Get the Tsar Object ID

        Returns:
            ObjectId -- List of ObjectId
        """
        try:
            return self._document["tsar"]
        except KeyError:
            return None

    # Class methods
    # ---------------------------------------------------------------------------------------------
    @classmethod
    async def create(cls, discord_bot, mongo_client, guild):
        self = MongoGame(mongo_client)
        self._bot = discord_bot
        self._set_default_values()
        await self._get(guild.id)
        return self

    # Private methods
    # ---------------------------------------------------------------------------------------------
    async def _get(self, guild):
        """Get the Mongo document by searching the guild

        Arguments:
            guild {int} -- Guild ID
        """
        document = await self._collection.find_one(dict(guild=guild))
        if document:
            self._document = document

    def _set_default_values(self):
        """Set default values for a new document"""
        self._document["guild"] = int()
        self._document["category"] = int()
        self._document["board"] = int()
        self._document["players"] = list()
        self._document["black_cards"] = list()
        self._document["white_cards"] = list()
        self._document["points"] = 5
        self._document["playing"] = False
        self._document["voting"] = "nobody"
        self._document["results"] = list()
        self._document["tsar"] = int()

    # Public methods
    # ---------------------------------------------------------------------------------------------
    async def get_players(self):
        """Get players

        Returns:
            *MongoPlayer -- List of players in the game
        """
        players = list()
        for player_id in self.players_id:
            player = await MongoPlayer.create(self._bot, self._client, player_id)
            players.append(player)
        return players

    async def add_player(self, player):
        """Add a player's id to the list of players

        Arguments:
            player {MongoPlayer} -- MongoPlayer to add

        Raises:
            TypeError -- Wrong type for player
        """
        if not isinstance(player, MongoPlayer):
            raise TypeError("Wrong type for player")
        self._document["players"].append(player.document_id)
        await self.save()

    async def delete_player(self, player):
        """Remove a player's id to the list of players

        Arguments:
            player {MongoPlayer} -- MongoPlayer to remove

        Raises:
            TypeError -- Wrong for player
        """
        if not isinstance(player, MongoPlayer):
            raise TypeError("Wrong type for player")
        self._document["players"].remove(player.document_id)
        await self.save()

    async def get_players_answers(self):
        """Count the number of player who has answered

        Returns:
            int -- Number of player who has voted
        """

        count = 0
        players = await self.get_players()
        for player in players:
            if not player.document_id != self.tsar_id:
                if player.answers_id:
                    count += 1
        return count

    async def get_players_score(self):
        """Get the players and their score

        Returns:
            list -- List of Players and score
        """
        scores = list()
        players = await self.get_players()
        for player in players:
            scores.append([player, player.score])
        return scores

    async def is_points_max(self):
        """Checks if one player got the max score

        Returns:
            bool -- True/False
        """
        scores = await self.get_players_score()
        return not all(score < self.points for player, score in scores)

    async def score(self):
        pass

    async def get_black_card(self):
        """Get the last black card drawed

        Returns:
            MongoBlackCard -- Last black card drawed
        """
        black_card_id = self.black_cards_id[-1]
        black_card = await MongoBlackCard.create(self._client, black_card_id)
        return black_card

    async def draw_black_card(self):
        """Draw a new Black Card and send it to the board"""
        # Get a new Black Card
        query = [{"$sample": {"size": 1}}]
        card_number = len(self.black_cards_id)
        while len(self.black_cards_id) is card_number:
            async for document in self._client[self._DATABASE]["black_cards"].aggregate(query):
                if document["_id"] not in self.black_cards_id:
                    self._document["black_cards"].append(document["_id"])
        await self.save()

        # Send Black Card to the board
        black_card = self.get_black_card()
        message = create_embed(dict(title="Question - Pick {}".format(black_card.pick),
                                    description=black_card.text))
        await self.board.send(embed=message)

    async def get_tsar(self):
        """Get the tsar player

        Returns:
            MongoPlayer - Tsar player
        """
        player = await MongoPlayer.create(self._bot, self._client, self.tsar_id)
        return player

    async def set_random_tsar(self):
        """Set a new random tsar"""
        self._document["tsar"] = sample(self.players_id, 1)[0]  # Sample returns a list
        await self.save()

    async def get_tsar_answer(self):
        """Returns if the tsar has voted

        Returns:
            bool -- Tsar has voted
        """
        tsar = await self.get_tsar()
        if tsar.tsar_choice:
            return True
        return False

    async def send_answers(self):
        """Create proposals and send them to the board"""
        # Combine Black Cards and MongoPlayer answers
        results = list()
        black_card = await self.get_black_card()
        async for player in self.get_players():
            if player.document_id != self.tsar_id:
                answers = list()
                for answer in player.answers:
                    self._document["white_cards"].append(answer.document_id)
                    answers.append(answer.text)
                result = black_card.text.format(*answers)
                results.append([player.document_id, result])
                await player.delete_answers()
        shuffle(results)
        self._document["results"] = results
        await self.save()

        # Send answers to the board
        proposals = str()
        for index, value in enumerate(self._document["results"]):
            proposals += "{}. {}".format(index + 1, value[1])
        embed = create_embed(dict(fields=dict(name="Proposals", value=proposals.rstrip(),
                                              inline=False)))
        await self.board.send(embed=embed)

    async def wait_for_players_answers(self):
        """Waiting for all players, except the tsar, to vote"""
        self.voting = "players"
        await self.save()

        await self.board.send("Time to vote ! \
Vote in your private channel by using `{}vote`".format(self._bot.command_prefix))

        number_of_answers = await self.get_players_answers()
        while number_of_answers is not len(self.players_id) - 1:
            await sleep(5)
            number_of_answers = await self.get_players_answers()

        self.voting = "nobody"
        await self.save()

    async def wait_for_tsar_answer(self):
        """Wait for tsar to vote"""
        self.voting = "tsar"
        await self.save()

        await self.board.send("Time for tsar to decide ! \
Vote in your private channel by using `{}vote`".format(self._bot.command_prefix))

        tsar_answer = await self.get_tsar_answer()
        while not tsar_answer:
            await sleep(5)
            tsar_answer = await self.get_tsar_answer()

        self.voting = "nobody"
        await self.save()

    async def select_winner(self):
        """Update the score of winner player and set it to tsar"""
        tsar = await self.get_tsar()
        tsar_choice = tsar.tsar_choice
        await tsar.delete_choice()

        player_id = self._document["results"][tsar_choice - 1][0]
        player = await MongoPlayer.create(self._bot, self._client, player_id)
        player.score += 1
        await player.save()

        self._document["tsar"] = player_id
        await self.save()
        await self.board.send("{} have won this round !".format(player.user.mention))
