#!/usr/bin/env python

"""Card Against Humanity's player class"""

from discord import Guild, Member, TextChannel

from utils.embed import create_embed
from utils.mongodoc import MongoDocument
from .cards import WhiteCard


class Player(MongoDocument):
    """Data class for Player Mongo document"""

    _DATABASE = "cards_against_humanity"
    _COLLECTION = "players"
    _WHITE_CARDS_NUMBER = 7

    def __init__(self, discord_bot, mongo_client, document_id=None, user=None):
        super(Player, self).__init__(mongo_client)
        self._bot = discord_bot
        self._set_default_values()
        if document_id:
            self.get(document_id)
        if user:
            self._get(user)

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
    def white_cards(self):
        """Get white cards

        Returns:
            *WhiteCard -- List of WhiteCard
        """
        try:
            return [WhiteCard(self._client, _id) for _id in self._document["white_cards"]]
        except KeyError:
            return None

    @property
    def answers(self):
        """Get the answers

        Returns:
            *WhiteCard -- List of WhiteCard
        """
        try:
            return [WhiteCard(self._client, _id) for _id in self._document["answers"]]
        except KeyError:
            return None

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


    # Private methods
    # ---------------------------------------------------------------------------------------------
    def _get(self, user):
        document = self._collection.find_one(dict(user=user.id))
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

    # Public Methods
    # ---------------------------------------------------------------------------------------------
    def draw_white_cards(self, used_cards):
        """Draw white cards and sent them to the player

        Arguments:
            used_cards {*ObjectId} -- List of white cards already used by all players
        """
        # Get cards from MongoDB
        query = [{"$sample": {"size": 1}}]
        while not len(self.white_cards) is self._WHITE_CARDS_NUMBER:
            results = self._client[self._DATABASE]["white_cards"].aggregate(query)
            for document in results:
                if document["_id"] not in used_cards:
                    self._document["white_cards"].append(document["_id"])
        self.save()

    async def send_white_cards(self):
        """Send White cards to the player's channel"""
        fields = list()
        for index, card in enumerate(self.white_cards):
            fields.append(dict(name=(index + 1), value=card.text, inline=False))
        message = create_embed(dict(title="Answers", fields=fields))
        await self.channel.send(embed=message)

    def add_answers(self, answers):
        """Store answers given by the player

        Arguments:
            answers {*int} -- List of choices [1-7]
        """
        # Store answers in the same order
        for answer in answers:
            self._document["answers"].append(self._document["white_cards"][answer - 1])
        # Delete answer from player's white cards
        for answer in sorted(answers, reverse=True):
            del self._document["white_cards"][answer - 1]
        self.save()  # Save MongoDB document

    def clear_answers(self):
        """Clear answer for the player"""
        self._document["answers"] = list()
        self.save()
