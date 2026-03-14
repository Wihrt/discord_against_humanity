"""Card document classes for Cards Against Humanity."""

import logging
from typing import Self

from html2text import html2text
from motor.motor_asyncio import AsyncIOMotorClient

from discord_against_humanity.infrastructure.mongo import MongoDocument

logger = logging.getLogger(__name__)

_DEFAULT_PICK = 1


class MongoBlackCard(MongoDocument):
    """Data class for a Black Card (question) MongoDB document."""

    _DATABASE = "cards_against_humanity"
    _COLLECTION = "black_cards"

    @property
    def text(self) -> str | None:
        """Get the formatted card text.

        Returns:
            The card text with blanks formatted for display, or None.
        """
        try:
            pick = self.pick or _DEFAULT_PICK
            if "_" not in self._document["text"]:
                return html2text(
                    self._document["text"] + "**{}**. " * pick
                )
            return html2text(self._document["text"].replace("_", "**{}**"))
        except KeyError:
            return None

    @property
    def pick(self) -> int:
        """Get the number of cards to pick.

        Returns:
            The number of white cards a player must pick (defaults to 1).
        """
        return self._document.get("pick", _DEFAULT_PICK)

    @classmethod
    async def create(
        cls,
        mongo_client: AsyncIOMotorClient,  # type: ignore[type-arg]
        document_id: object = None,
    ) -> Self:
        """Create a new MongoBlackCard instance.

        Args:
            mongo_client: Motor client connected to the database.
            document_id: Optional ObjectId of the document to load.

        Returns:
            A new MongoBlackCard instance.
        """
        self = MongoBlackCard(mongo_client)
        if document_id:
            await self.get(document_id)
        return self


class MongoWhiteCard(MongoDocument):
    """Data class for a White Card (answer) MongoDB document."""

    _DATABASE = "cards_against_humanity"
    _COLLECTION = "white_cards"

    @property
    def text(self) -> str | None:
        """Get the card text.

        Returns:
            The card text converted from HTML, or None.
        """
        try:
            return html2text(self._document["text"]).rstrip()
        except KeyError:
            return None

    @classmethod
    async def create(
        cls,
        mongo_client: AsyncIOMotorClient,  # type: ignore[type-arg]
        document_id: object = None,
    ) -> Self:
        """Create a new MongoWhiteCard instance.

        Args:
            mongo_client: Motor client connected to the database.
            document_id: Optional ObjectId of the document to load.

        Returns:
            A new MongoWhiteCard instance.
        """
        self = MongoWhiteCard(mongo_client)
        if document_id:
            await self.get(document_id)
        return self
