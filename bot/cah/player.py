#!/usr/bin/env python

"""Card Against Humanity's player class"""

from logging import getLogger

from discord import Guild, Member, TextChannel

from utils.embed import create_embed
from utils.mongodoc import MongoDocument
from .cards import MongoWhiteCard

LOGGER = getLogger(__name__)

class MongoPlayer(MongoDocument):
    """Class for Player Mongo Document"""

    _DATABASE = "cards_against_humanity"
    _COLLECTION = "players"
    _WHITE_CARDS_NUMBER = 7

    # Properties
    # ---------------------------------------------------------------------------------------------
    @property
    def guild(self):
        """Get the Guild

        Returns:
            Guild -- Player's guild
        """
        try:
            return self._bot.get_guild(self._document["guild"])
        except KeyError:
            return None

    @guild.setter
    def guild(self, value):
        """Set the Guild

        Arguments:
            value {Guild} -- Player's guild

        Raises:
            TypeError -- Wrong type
        """
        if not isinstance(value, Guild):
            raise TypeError("Wrong type for value : %s" % type(value))
        self._document["guild"] = value.id

    @property
    def user(self):
        """Get the member

        Returns:
            Member -- Player's member
        """
        try:
            return self.guild.get_member(self._document["user"])
        except (AttributeError, KeyError):
            return None

    @user.setter
    def user(self, value):
        """Set the Member

        Arguments:
            value {Member} -- Player's member

        Raises:
            TypeError -- Wrong type
        """
        if not isinstance(value, Member):
            raise TypeError("Wrong type for value : %s" % type(value))
        self._document["user"] = value.id

    @property
    def channel(self):
        """Get channel

        Returns:
            TextChannel -- Player's channel
        """
        try:
            return self.guild.get_channel(self._document["channel"])
        except (AttributeError, KeyError):
            return None

    @channel.setter
    def channel(self, value):
        """Set channel

        Arguments:
            value {TextChannel} -- Player's channel

        Raises:
            TypeError -- Wrong type
        """
        if not isinstance(value, TextChannel):
            raise TypeError("Wrong type for value : %s" % type(value))
        self._document["channel"] = value.id

    @property
    def score(self):
        """Get score

        Returns:
            int -- Player's score
        """
        try:
            return self._document["score"]
        except KeyError:
            return None

    @score.setter
    def score(self, value):
        """Set score

        Arguments:
            value {int} -- Player's score

        Raises:
            TypeError -- Wrong type
        """
        if not isinstance(value, int):
            raise TypeError("Wrong type for value : %s" % type(value))
        self._document["score"] = value

    @property
    def tsar_choice(self):
        try:
            return self._document["tsar_choice"]
        except KeyError:
            return None

    @tsar_choice.setter
    def tsar_choice(self, value):
        if not isinstance(value, int):
            raise TypeError("Wrong type for value : %s" % type(value))
        self._document["tsar_choice"] = value

    @property
    def white_cards_id(self):
        """Get white cards

        Returns:
            *MongoWhiteCard -- List of MongoWhiteCard
        """
        try:
            return self._document["white_cards"]
        except KeyError:
            return None

    @property
    def answers_id(self):
        """Get the answers

        Returns:
            *MongoWhiteCard -- List of MongoWhiteCard
        """
        try:
            return self._document["answers"]
        except KeyError:
            return None

    # Class methods
    # ---------------------------------------------------------------------------------------------
    @classmethod
    async def create(cls, discord_bot, mongo_client, document_id=None, user=None):
        self = MongoPlayer(mongo_client)
        self._bot = discord_bot
        self._set_default_values()
        if document_id:
            await self.get(document_id)
        if user:
            await self._get(user)
        return self

    # Private methods
    # ---------------------------------------------------------------------------------------------
    async def _get(self, user):
        """Get the document by searching with the User Id

        Arguments:
            user {Member} -- User to search

        Raises:
            TypeError -- Wrong type for user
        """
        if not isinstance(user, Member):
            raise TypeError("Wrong type for user")
        document = await self._collection.find_one(dict(user=user.id))
        if document:
            self._document = document

    def _set_default_values(self):
        self._document["guild"] = int()
        self._document["user"] = int()
        self._document["channel"] = int()
        self._document["score"] = 0
        self._document["answers"] = list()
        self._document["white_cards"] = list()
        self._document["tsar_choice"] = 0

    # Public methods
    # ---------------------------------------------------------------------------------------------
    async def get_white_cards(self):
        """Get the White Cards

        Returns:
            *MongoWhiteCard -- List of MongoWhiteCards
        """
        cards = list()
        for card_id in self.white_cards_id:
            card = await MongoWhiteCard.create(self._client, card_id)
            cards.append(card)
        return cards

    async def draw_white_cards(self, used_cards):
        """Draw white cards for the player

        Arguments:
            used_cards {*ObjectId} -- ObjectId of used cards
        """
        query = [{"$sample": {"size": 1}}]
        while not len(self.white_cards_id) is self._WHITE_CARDS_NUMBER:
            async for document in self._client[self._DATABASE]["white_cards"].aggregate(query):
                if document["_id"] not in used_cards:
                    self._document["white_cards"].append(document["_id"])
        await self.save()

        proposals = str()
        white_cards = await self.get_white_cards()
        for index, card in enumerate(white_cards):
            proposals += "{}. {}\n".format(index + 1, card.text)
        embed = create_embed(dict(fields=dict(name="Answers", value=proposals.rstrip(),
                                              inline=False)))
        await self.channel.send(embed=embed)

    async def get_answers(self):
        """Get the White Cards answers

        Returns:
            *MongoWhiteCard -- List of MongoWhiteCards
        """
        cards = list()
        for card_id in self.answers_id:
            card = await MongoWhiteCard.create(self._client, card_id)
            cards.append(card)
        return cards

    async def add_answers(self, answers):
        """Store answers given by the player

        Arguments:
            answers {*int} -- List of choices [1-7]
        """
        for answer in answers:
            self._document["answers"].append(self.white_cards_id[answer - 1])
        for answer in sorted(answers, reverse=True):
            del self.white_cards_id[answer - 1]
        await self.save()

    async def delete_answers(self):
        """Delete answers for the player"""
        self._document["answers"] = list()
        await self.save()

    async def delete_choice(self):
        """Delete choice for the player"""
        self.tsar_choice = 0
        await self.save()
