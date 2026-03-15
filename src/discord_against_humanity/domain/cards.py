"""Card document classes for Cards Against Humanity."""

import logging
from typing import Self

import valkey.asyncio as valkey
from html2text import html2text

from discord_against_humanity.infrastructure.valkey import ValkeyDocument

logger = logging.getLogger(__name__)

_DEFAULT_PICK = 1


class ValkeyBlackCard(ValkeyDocument):
    """Data class for a Black Card (question) Valkey document."""

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
        valkey_client: valkey.Valkey,
        document_id: str | None = None,
    ) -> Self:
        """Create a new ValkeyBlackCard instance.

        Args:
            valkey_client: Async Valkey client.
            document_id: Optional ID of the document to load.

        Returns:
            A new ValkeyBlackCard instance.
        """
        self = ValkeyBlackCard(valkey_client)
        if document_id:
            await self.get(document_id)
        return self


class ValkeyWhiteCard(ValkeyDocument):
    """Data class for a White Card (answer) Valkey document."""

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
        valkey_client: valkey.Valkey,
        document_id: str | None = None,
    ) -> Self:
        """Create a new ValkeyWhiteCard instance.

        Args:
            valkey_client: Async Valkey client.
            document_id: Optional ID of the document to load.

        Returns:
            A new ValkeyWhiteCard instance.
        """
        self = ValkeyWhiteCard(valkey_client)
        if document_id:
            await self.get(document_id)
        return self
