"""Player state and actions for Cards Against Humanity."""

import logging
from typing import Any, Self

import discord
from discord import Guild, Member, TextChannel
from discord.ext.commands import Bot
from motor.motor_asyncio import AsyncIOMotorClient

from discord_against_humanity.domain.cards import MongoWhiteCard
from discord_against_humanity.infrastructure.mongo import MongoDocument
from discord_against_humanity.utils.debug import async_log_event
from discord_against_humanity.utils.embed import create_embed

logger = logging.getLogger(__name__)

_WHITE_CARDS_NUMBER = 7


class MongoPlayer(MongoDocument):
    """MongoDB document class for a Cards Against Humanity player."""

    _DATABASE = "cards_against_humanity"
    _COLLECTION = "players"

    # Properties
    # -------------------------------------------------------------------------

    @property
    def guild(self) -> Guild | None:
        """Get the guild this player belongs to.

        Returns:
            The Discord guild, or None.
        """
        try:
            return self._bot.get_guild(self._document["guild"])
        except KeyError:
            return None

    @guild.setter
    def guild(self, value: Guild) -> None:
        """Set the guild for this player.

        Args:
            value: The Discord guild.

        Raises:
            TypeError: If value is not a Guild.
        """
        if not isinstance(value, Guild):
            raise TypeError(f"Wrong type for value: {type(value)}")
        self._document["guild"] = value.id

    @property
    def user(self) -> Member | None:
        """Get the Discord member for this player.

        Returns:
            The Discord member, or None.
        """
        try:
            guild = self.guild
            if guild is None:
                return None
            return guild.get_member(self._document["user"])
        except (AttributeError, KeyError):
            return None

    @user.setter
    def user(self, value: Member) -> None:
        """Set the Discord member for this player.

        Args:
            value: The Discord member.

        Raises:
            TypeError: If value is not a Member.
        """
        if not isinstance(value, Member):
            raise TypeError(f"Wrong type for value: {type(value)}")
        self._document["user"] = value.id

    @property
    def channel(self) -> TextChannel | None:
        """Get the player's private text channel.

        Returns:
            The player's text channel, or None.
        """
        try:
            guild = self.guild
            if guild is None:
                return None
            return guild.get_channel(self._document["channel"])  # type: ignore[return-value]
        except (AttributeError, KeyError):
            return None

    @channel.setter
    def channel(self, value: TextChannel) -> None:
        """Set the player's private text channel.

        Args:
            value: The text channel.

        Raises:
            TypeError: If value is not a TextChannel.
        """
        if not isinstance(value, TextChannel):
            raise TypeError(f"Wrong type for value: {type(value)}")
        self._document["channel"] = value.id

    @property
    def score(self) -> int | None:
        """Get the player's score.

        Returns:
            The player's current score, or None.
        """
        try:
            return self._document["score"]
        except KeyError:
            return None

    @score.setter
    def score(self, value: int) -> None:
        """Set the player's score.

        Args:
            value: The new score.

        Raises:
            TypeError: If value is not an int.
        """
        if not isinstance(value, int):
            raise TypeError(f"Wrong type for value: {type(value)}")
        self._document["score"] = value

    @property
    def tsar_choice(self) -> int | None:
        """Get the tsar's choice.

        Returns:
            The tsar's chosen answer index, or None.
        """
        try:
            return self._document["tsar_choice"]
        except KeyError:
            return None

    @tsar_choice.setter
    def tsar_choice(self, value: int) -> None:
        """Set the tsar's choice.

        Args:
            value: The chosen answer index.

        Raises:
            TypeError: If value is not an int.
        """
        if not isinstance(value, int):
            raise TypeError(f"Wrong type for value: {type(value)}")
        self._document["tsar_choice"] = value

    @property
    def white_cards_id(self) -> list[Any] | None:
        """Get the list of white card ObjectIds in hand.

        Returns:
            List of white card ObjectIds, or None.
        """
        try:
            return self._document["white_cards"]
        except KeyError:
            return None

    @property
    def answers_id(self) -> list[Any] | None:
        """Get the list of answer card ObjectIds.

        Returns:
            List of selected answer ObjectIds, or None.
        """
        try:
            return self._document["answers"]
        except KeyError:
            return None

    # Class methods
    # -------------------------------------------------------------------------

    @classmethod
    async def create(
        cls,
        discord_bot: Bot,
        mongo_client: AsyncIOMotorClient,  # type: ignore[type-arg]
        document_id: object = None,
        user: Member | discord.User | None = None,
        guild: Guild | None = None,
    ) -> Self:
        """Create a new MongoPlayer instance.

        Args:
            discord_bot: The Discord bot instance.
            mongo_client: Motor client connected to the database.
            document_id: Optional ObjectId to load an existing player.
            user: Optional Discord Member/User to look up an existing player.
            guild: Optional Discord Guild to resolve member from user.

        Returns:
            A new MongoPlayer instance.
        """
        self = MongoPlayer(mongo_client)
        self._bot = discord_bot
        self._set_default_values()
        if document_id:
            await self.get(document_id)
        if user:
            # Resolve to Member if we have a guild and a bare User
            member = user
            if guild is not None and not isinstance(user, Member):
                resolved = guild.get_member(user.id)
                if resolved is not None:
                    member = resolved
            if isinstance(member, Member):
                await self._get(member)
        logger.debug("Player Document: %s", self._document)
        return self

    # Private methods
    # -------------------------------------------------------------------------

    async def _get(self, user: Member) -> None:
        """Load the player document by Discord user.

        Args:
            user: The Discord member to search for.

        Raises:
            TypeError: If user is not a Member.
        """
        if not isinstance(user, Member):
            raise TypeError("Wrong type for user")
        document = await self._repo.find_one({"user": user.id})
        if document:
            self._document = document

    def _set_default_values(self) -> None:
        """Set default values for a new player document."""
        self._document["guild"] = 0
        self._document["user"] = 0
        self._document["channel"] = 0
        self._document["score"] = 0
        self._document["answers"] = []
        self._document["white_cards"] = []
        self._document["tsar_choice"] = 0

    # Public methods
    # -------------------------------------------------------------------------

    @async_log_event
    async def get_white_cards(self) -> list[MongoWhiteCard]:
        """Get the white cards in this player's hand.

        Returns:
            List of MongoWhiteCard instances.
        """
        cards: list[MongoWhiteCard] = []
        for card_id in self.white_cards_id:  # type: ignore[union-attr]
            card = await MongoWhiteCard.create(self._client, card_id)
            cards.append(card)
        return cards

    @async_log_event
    async def draw_white_cards(self, used_cards: list[Any]) -> None:
        """Draw white cards until the player has a full hand.

        Prevents drawing duplicates already in hand or in
        the global used-cards list.  Stops after a maximum number
        of attempts to avoid an infinite loop when the deck is
        nearly exhausted.

        Args:
            used_cards: List of ObjectIds for already-used cards.
        """
        from discord_against_humanity.infrastructure.mongo import (
            MongoRepository,
        )

        max_attempts = 200
        attempts = 0
        wc_repo = MongoRepository(
            self._client, self._DATABASE, "white_cards"
        )
        while len(self.white_cards_id) != _WHITE_CARDS_NUMBER:  # type: ignore[arg-type]
            attempts += 1
            if attempts > max_attempts:
                logger.warning(
                    "Could not fill hand: deck may be exhausted"
                )
                break
            results = await wc_repo.aggregate(
                [{"$sample": {"size": 1}}]
            )
            for document in results:
                card_id = document["_id"]
                if (
                    card_id not in used_cards
                    and card_id not in self.white_cards_id  # type: ignore[operator]
                ):
                    self._document["white_cards"].append(card_id)
        await self.save()

        proposals = ""
        white_cards = await self.get_white_cards()
        for index, card in enumerate(white_cards):
            proposals += f"{index + 1}. {card.text}\n"
        embed = create_embed(
            {
                "fields": {
                    "name": "Answers",
                    "value": proposals.rstrip(),
                    "inline": False,
                }
            }
        )
        await self.channel.send(embed=embed)  # type: ignore[union-attr]

    @async_log_event
    async def get_answers(self) -> list[MongoWhiteCard]:
        """Get the white cards selected as answers.

        Returns:
            List of MongoWhiteCard instances.
        """
        cards: list[MongoWhiteCard] = []
        for card_id in self.answers_id:  # type: ignore[union-attr]
            card = await MongoWhiteCard.create(self._client, card_id)
            cards.append(card)
        return cards

    @async_log_event
    async def add_answers(self, answers: list[int]) -> None:
        """Store the player's answer choices and remove cards from hand.

        Args:
            answers: List of card indices (1-based) chosen by the player.
        """
        for answer in answers:
            self._document["answers"].append(self.white_cards_id[answer - 1])  # type: ignore[index]
        for answer in sorted(answers, reverse=True):
            del self.white_cards_id[answer - 1]  # type: ignore[index]
        await self.save()

    @async_log_event
    async def delete_answers(self) -> None:
        """Clear the player's stored answers."""
        self._document["answers"] = []
        await self.save()

    @async_log_event
    async def delete_choice(self) -> None:
        """Clear the tsar's choice."""
        self.tsar_choice = 0
        await self.save()
