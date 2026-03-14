"""Game state and logic for Cards Against Humanity."""

import logging
from asyncio import sleep
from random import sample, shuffle
from typing import Any, Self

from discord import CategoryChannel, Guild, TextChannel
from discord.ext.commands import Bot
from motor.motor_asyncio import AsyncIOMotorClient

from discord_against_humanity.domain.cards import MongoBlackCard
from discord_against_humanity.domain.player import MongoPlayer
from discord_against_humanity.infrastructure.mongo import MongoDocument
from discord_against_humanity.utils.debug import async_log_event
from discord_against_humanity.utils.embed import create_embed

logger = logging.getLogger(__name__)


class MongoGame(MongoDocument):
    """MongoDB document class for a Cards Against Humanity game."""

    _DATABASE = "cards_against_humanity"
    _COLLECTION = "games"

    # Properties
    # -------------------------------------------------------------------------

    @property
    def guild(self) -> Guild | None:
        """Get the guild this game belongs to.

        Returns:
            The Discord guild, or None.
        """
        try:
            return self._bot.get_guild(self._document["guild"])
        except KeyError:
            return None

    @guild.setter
    def guild(self, value: Guild) -> None:
        """Set the guild for this game.

        Args:
            value: The Discord guild.

        Raises:
            TypeError: If value is not a Guild.
        """
        if not isinstance(value, Guild):
            raise TypeError(f"Wrong type for value: {type(value)}")
        self._document["guild"] = value.id

    @property
    def category(self) -> CategoryChannel | None:
        """Get the category channel for this game.

        Returns:
            The category channel, or None.
        """
        try:
            guild = self.guild
            if guild is None:
                return None
            return guild.get_channel(self._document["category"])  # type: ignore[return-value]
        except (AttributeError, KeyError):
            return None

    @category.setter
    def category(self, value: CategoryChannel) -> None:
        """Set the category channel for this game.

        Args:
            value: The category channel.

        Raises:
            TypeError: If value is not a CategoryChannel.
        """
        if not isinstance(value, CategoryChannel):
            raise TypeError(f"Wrong type for value: {type(value)}")
        self._document["category"] = value.id

    @property
    def board(self) -> TextChannel | None:
        """Get the board text channel for this game.

        Returns:
            The board channel, or None.
        """
        try:
            guild = self.guild
            if guild is None:
                return None
            return guild.get_channel(self._document["board"])  # type: ignore[return-value]
        except (AttributeError, KeyError):
            return None

    @board.setter
    def board(self, value: TextChannel) -> None:
        """Set the board text channel for this game.

        Args:
            value: The board channel.

        Raises:
            TypeError: If value is not a TextChannel.
        """
        if not isinstance(value, TextChannel):
            raise TypeError(f"Wrong type for value: {type(value)}")
        self._document["board"] = value.id

    @property
    def points(self) -> int | None:
        """Get the maximum number of points to win.

        Returns:
            The point threshold, or None.
        """
        try:
            return self._document["points"]
        except KeyError:
            return None

    @points.setter
    def points(self, value: int) -> None:
        """Set the maximum number of points to win.

        Args:
            value: The point threshold.

        Raises:
            TypeError: If value is not an int.
        """
        if not isinstance(value, int):
            raise TypeError(f"Wrong type for value: {type(value)}")
        self._document["points"] = value

    @property
    def playing(self) -> bool | None:
        """Get the game's playing status.

        Returns:
            Whether the game is in progress, or None.
        """
        try:
            return self._document["playing"]
        except KeyError:
            return None

    @playing.setter
    def playing(self, value: bool) -> None:
        """Set the game's playing status.

        Args:
            value: Whether the game is in progress.

        Raises:
            TypeError: If value is not a bool.
        """
        if not isinstance(value, bool):
            raise TypeError(f"Wrong type for value: {type(value)}")
        self._document["playing"] = value

    @property
    def voting(self) -> str | None:
        """Get the current voting status.

        Returns:
            Who is currently voting ('players', 'tsar', or 'nobody'), or None.
        """
        try:
            return self._document["voting"]
        except KeyError:
            return None

    @voting.setter
    def voting(self, value: str) -> None:
        """Set the current voting status.

        Args:
            value: Who should vote ('players', 'tsar', or 'nobody').

        Raises:
            TypeError: If value is not a str.
            ValueError: If value is not a valid voting status.
        """
        if not isinstance(value, str):
            raise TypeError(f"Wrong type for value: {type(value)}")
        if value not in ("players", "tsar", "nobody"):
            raise ValueError("Wrong value for voting")
        self._document["voting"] = value

    @property
    def players_id(self) -> list[Any] | None:
        """Get the list of player ObjectIds.

        Returns:
            List of player ObjectIds, or None.
        """
        try:
            return self._document["players"]
        except KeyError:
            return None

    @property
    def black_cards_id(self) -> list[Any] | None:
        """Get the list of used Black Card ObjectIds.

        Returns:
            List of used black card ObjectIds, or None.
        """
        try:
            return self._document["black_cards"]
        except KeyError:
            return None

    @property
    def white_cards_id(self) -> list[Any] | None:
        """Get the list of used White Card ObjectIds.

        Returns:
            List of used white card ObjectIds, or None.
        """
        try:
            return self._document["white_cards"]
        except KeyError:
            return None

    @property
    def tsar_id(self) -> Any | None:
        """Get the current Tsar's ObjectId.

        Returns:
            The tsar's ObjectId, or None.
        """
        try:
            return self._document["tsar"]
        except KeyError:
            return None

    # Class methods
    # -------------------------------------------------------------------------

    @classmethod
    async def create(
        cls,
        discord_bot: Bot,
        mongo_client: AsyncIOMotorClient,  # type: ignore[type-arg]
        guild: Guild,
    ) -> Self:
        """Create a new MongoGame instance.

        Args:
            discord_bot: The Discord bot instance.
            mongo_client: Motor client connected to the database.
            guild: The Discord guild for this game.

        Returns:
            A new MongoGame instance.
        """
        self = MongoGame(mongo_client)
        self._bot = discord_bot
        self._set_default_values()
        await self._get(guild.id)
        return self

    # Private methods
    # -------------------------------------------------------------------------

    async def _get(self, guild: int) -> None:
        """Load the game document by guild ID.

        Args:
            guild: The guild ID to search for.
        """
        document = await self._collection.find_one({"guild": guild})
        if document:
            self._document = document

    def _set_default_values(self) -> None:
        """Set default values for a new game document."""
        self._document["guild"] = 0
        self._document["category"] = 0
        self._document["board"] = 0
        self._document["players"] = []
        self._document["black_cards"] = []
        self._document["white_cards"] = []
        self._document["points"] = 5
        self._document["playing"] = False
        self._document["voting"] = "nobody"
        self._document["results"] = []
        self._document["tsar"] = 0

    # Public methods
    # -------------------------------------------------------------------------

    @async_log_event
    async def get_players(self) -> list[MongoPlayer]:
        """Get all players in this game.

        Returns:
            List of MongoPlayer instances.
        """
        players: list[MongoPlayer] = []
        for player_id in self.players_id:  # type: ignore[union-attr]
            player = await MongoPlayer.create(self._bot, self._client, player_id)
            players.append(player)
        return players

    @async_log_event
    async def add_player(self, player: MongoPlayer) -> None:
        """Add a player to the game.

        Args:
            player: The player to add.

        Raises:
            TypeError: If player is not a MongoPlayer.
        """
        if not isinstance(player, MongoPlayer):
            raise TypeError("Wrong type for player")
        self._document["players"].append(player.document_id)
        await self.save()

    @async_log_event
    async def delete_player(self, player: MongoPlayer) -> None:
        """Remove a player from the game.

        Args:
            player: The player to remove.

        Raises:
            TypeError: If player is not a MongoPlayer.
        """
        if not isinstance(player, MongoPlayer):
            raise TypeError("Wrong type for player")
        self._document["players"].remove(player.document_id)
        await self.save()

    @async_log_event
    async def get_players_answers(self) -> int:
        """Count the number of players who have answered.

        Returns:
            Number of players who have voted.
        """
        count = 0
        players = await self.get_players()
        for player in players:
            if player.document_id != self.tsar_id:
                if player.answers_id:
                    count += 1
        return count

    @async_log_event
    async def get_players_score(self) -> list[list[Any]]:
        """Get all players and their scores.

        Returns:
            List of [player, score] pairs.
        """
        scores: list[list[Any]] = []
        players = await self.get_players()
        for player in players:
            scores.append([player, player.score])
        return scores

    @async_log_event
    async def is_points_max(self) -> bool:
        """Check if any player has reached the maximum score.

        Returns:
            True if a player has reached the win threshold.
        """
        scores = await self.get_players_score()
        return not all(score < self.points for _player, score in scores)

    @async_log_event
    async def score(self) -> None:
        """Display the current scoreboard in the board channel."""
        scores = await self.get_players_score()
        fields: list[dict[str, Any]] = []
        for player, score in scores:
            fields.append(
                {"name": player.user.display_name, "value": score, "inline": True}
            )
        message = create_embed({"title": "Score", "fields": fields})
        await self.board.send(embed=message)  # type: ignore[union-attr]

    @async_log_event
    async def get_black_card(self) -> MongoBlackCard:
        """Get the last drawn black card.

        Returns:
            The most recently drawn MongoBlackCard.
        """
        black_card_id = self.black_cards_id[-1]  # type: ignore[index]
        black_card = await MongoBlackCard.create(self._client, black_card_id)
        return black_card

    @async_log_event
    async def draw_black_card(self) -> Any:
        """Draw a new black card and return its embed message.

        Returns:
            A Discord Embed with the black card question.
        """
        query = [{"$sample": {"size": 1}}]
        card_number = len(self.black_cards_id)  # type: ignore[arg-type]
        while len(self.black_cards_id) == card_number:  # type: ignore[arg-type]
            async for document in self._client[self._DATABASE]["black_cards"].aggregate(
                query
            ):
                if document["_id"] not in self.black_cards_id:  # type: ignore[operator]
                    self._document["black_cards"].append(document["_id"])
        await self.save()

        black_card = await self.get_black_card()
        message = create_embed(
            {
                "title": f"Question - Pick {black_card.pick}",
                "description": black_card.text,
            }
        )
        return message

    @async_log_event
    async def get_tsar(self) -> MongoPlayer:
        """Get the current tsar player.

        Returns:
            The tsar MongoPlayer instance.
        """
        player = await MongoPlayer.create(self._bot, self._client, self.tsar_id)
        return player

    @async_log_event
    async def set_random_tsar(self) -> None:
        """Set a new random tsar from the player list."""
        self._document["tsar"] = sample(self.players_id, 1)[0]  # type: ignore[arg-type]
        await self.save()

    @async_log_event
    async def get_tsar_answer(self) -> bool:
        """Check if the tsar has voted.

        Returns:
            True if the tsar has made a choice.
        """
        tsar = await self.get_tsar()
        if tsar.tsar_choice:
            return True
        return False

    @async_log_event
    async def send_answers(self) -> Any:
        """Combine player answers with the black card and send proposals.

        Returns:
            A Discord Embed with the shuffled proposals.
        """
        results: list[list[Any]] = []
        black_card = await self.get_black_card()
        players = await self.get_players()
        for player in players:
            if player.document_id != self.tsar_id:
                answers: list[str] = []
                player_answers = await player.get_answers()
                for answer in player_answers:
                    self._document["white_cards"].append(answer.document_id)
                    answers.append(answer.text)
                result = black_card.text.format(*answers)
                results.append([player.document_id, result])
                await player.delete_answers()
        shuffle(results)
        self._document["results"] = results
        await self.save()

        proposals = ""
        for index, value in enumerate(self._document["results"]):
            proposals += f"{index + 1}. {value[1]}\n"
        message = create_embed(
            {
                "fields": {
                    "name": "Proposals",
                    "value": proposals.rstrip(),
                    "inline": False,
                }
            }
        )
        return message

    @async_log_event
    async def wait_for_players_answers(self) -> None:
        """Wait for all non-tsar players to vote."""
        self.voting = "players"
        await self.save()

        await self.board.send(  # type: ignore[union-attr]
            f"Time to vote! Vote in your private channel by using "
            f"`{self._bot.command_prefix}vote`"
        )

        number_of_answers = await self.get_players_answers()
        while number_of_answers != len(self.players_id) - 1:  # type: ignore[arg-type]
            await sleep(5)
            number_of_answers = await self.get_players_answers()

        self.voting = "nobody"
        await self.save()

    @async_log_event
    async def wait_for_tsar_answer(self) -> None:
        """Wait for the tsar to vote."""
        self.voting = "tsar"
        await self.save()

        await self.board.send(  # type: ignore[union-attr]
            f"Time for tsar to decide! Vote in your private channel by using "
            f"`{self._bot.command_prefix}tsar`"
        )

        tsar_answer = await self.get_tsar_answer()
        while not tsar_answer:
            await sleep(5)
            tsar_answer = await self.get_tsar_answer()

        self.voting = "nobody"
        await self.save()

    @async_log_event
    async def select_winner(self) -> None:
        """Award a point to the winner and make them the next tsar."""
        tsar = await self.get_tsar()
        tsar_choice = tsar.tsar_choice
        await tsar.delete_choice()

        player_id = self._document["results"][tsar_choice - 1][0]
        player = await MongoPlayer.create(self._bot, self._client, player_id)
        player.score += 1
        await player.save()

        self._document["tsar"] = player_id
        await self.save()
        await self.board.send(  # type: ignore[union-attr]
            f"{player.user.mention} has won this round!"
        )
