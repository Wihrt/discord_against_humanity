#!/usr/bin/env python

"""Cards Mongo document classes"""

from html2text import html2text
from utils.mongodoc import MongoDocument

class MongoBlackCard(MongoDocument):
    """Data class for Black Card Mongo document"""

    _DATABASE = "cards_against_humanity"
    _COLLECTION = "black_cards"

    # Properties
    # ---------------------------------------------------------------------------------------------
    @property
    def text(self):
        """Get text

        Returns:
            str -- Text of the card
        """
        try:
            if "_" not in self._document["text"]:
                return html2text(self._document["text"] + "**{}**. " * self.pick)
            return html2text(self._document["text"].replace("_", "**{}**"))
        except KeyError:
            return None

    @property
    def pick(self):
        """Get number of cards to pick

        Returns:
            int -- Number of cards to pick
        """
        try:
            return self._document["pick"]
        except KeyError:
            return None

    # Class methods
    # ---------------------------------------------------------------------------------------------
    @classmethod
    async def create(cls, mongo_client, document_id=None):
        self = MongoBlackCard(mongo_client)
        if document_id:
            await self.get(document_id)
        return self

class MongoWhiteCard(MongoDocument):
    """Data class for White Card mongo document"""

    _DATABASE = "cards_against_humanity"
    _COLLECTION = "white_cards"

    # Properties
    # ---------------------------------------------------------------------------------------------
    @property
    def text(self):
        """Get text

        Returns:
            str -- Text of the card
        """
        try:
            return html2text(self._document["text"]).rstrip()
        except KeyError:
            return None

    # Class methods
    # ---------------------------------------------------------------------------------------------
    @classmethod
    async def create(cls, mongo_client, document_id=None):
        self = MongoWhiteCard(mongo_client)
        if document_id:
            await self.get(document_id)
        return self
