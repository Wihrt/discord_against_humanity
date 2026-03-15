"""Comprehensive game simulation — 5 players, 6 rounds."""

import random
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from discord_against_humanity.domain.game import Game
from discord_against_humanity.domain.player import Player
from discord_against_humanity.ports.repository import DocumentNotFoundError

# ── In-memory repository ─────────────────────────────────────────────────────


class InMemoryRepository:
    """Dict-backed Repository for deterministic testing."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._counter = 0

    async def find_by_id(self, document_id: str) -> dict[str, Any] | None:
        doc = self._store.get(document_id)
        return dict(doc) if doc is not None else None

    async def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        for doc in self._store.values():
            if all(doc.get(k) == v for k, v in query.items()):
                return dict(doc)
        return None

    async def insert(self, document: dict[str, Any]) -> str:
        if "_id" not in document or not document["_id"]:
            self._counter += 1
            document["_id"] = str(uuid4())
        doc_id = document["_id"]
        self._store[doc_id] = dict(document)
        return doc_id

    async def replace(
        self, document_id: str, document: dict[str, Any]
    ) -> dict[str, Any]:
        if document_id not in self._store:
            raise DocumentNotFoundError(document_id)
        document["_id"] = document_id
        self._store[document_id] = dict(document)
        return dict(document)

    async def delete_by_id(self, document_id: str) -> None:
        self._store.pop(document_id, None)

    async def random_member(self) -> dict[str, Any] | None:
        if not self._store:
            return None
        doc_id = random.choice(list(self._store.keys()))
        return dict(self._store[doc_id])

    async def count(self) -> int:
        return len(self._store)

    # helpers for test setup
    def seed(self, doc: dict[str, Any]) -> str:
        """Insert a document directly (sync) and return its ID."""
        doc_id = doc["_id"]
        self._store[doc_id] = dict(doc)
        return doc_id


# ── Helpers ──────────────────────────────────────────────────────────────────

NUM_PLAYERS = 5
NUM_ROUNDS = 6
GUILD_ID = 123456789
BOARD_CHANNEL_ID = 9999


def _make_repos() -> dict[str, InMemoryRepository]:
    return {
        "games": InMemoryRepository(),
        "players": InMemoryRepository(),
        "black_cards": InMemoryRepository(),
        "white_cards": InMemoryRepository(),
    }


def _seed_black_cards(repo: InMemoryRepository, n: int = 10) -> list[str]:
    """Pre-populate the black-cards collection and return their IDs."""
    ids: list[str] = []
    for i in range(n):
        card_id = f"bc-{i}"
        repo.seed(
            {"_id": card_id, "text": f"Why is _ question {i}?", "pick": 1}
        )
        ids.append(card_id)
    return ids


def _seed_white_cards(repo: InMemoryRepository, n: int = 60) -> list[str]:
    """Pre-populate the white-cards collection and return their IDs."""
    ids: list[str] = []
    for i in range(n):
        card_id = f"wc-{i}"
        repo.seed({"_id": card_id, "text": f"Answer {i}"})
        ids.append(card_id)
    return ids


def _build_mock_bot() -> MagicMock:
    """Create a mock bot wired to a guild with channels and members."""
    mock_guild = MagicMock()
    mock_guild.id = GUILD_ID

    channels: dict[int, MagicMock] = {}
    for i in range(NUM_PLAYERS):
        ch = MagicMock()
        ch.id = 2000 + i
        ch.send = AsyncMock()
        channels[2000 + i] = ch
    board = MagicMock()
    board.id = BOARD_CHANNEL_ID
    board.send = AsyncMock()
    channels[BOARD_CHANNEL_ID] = board

    members: dict[int, MagicMock] = {}
    for i in range(NUM_PLAYERS):
        m = MagicMock()
        m.id = 1000 + i
        m.display_name = f"Player{i + 1}"
        m.mention = f"<@{1000 + i}>"
        members[1000 + i] = m

    mock_guild.get_channel = MagicMock(
        side_effect=lambda cid: channels.get(cid)
    )
    mock_guild.get_member = MagicMock(
        side_effect=lambda uid: members.get(uid)
    )

    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=mock_guild)
    return bot


# ── Simulation test ─────────────────────────────────────────────────────────


async def test_full_game_simulation():
    """Simulate 6 rounds with 5 players, verifying scores and card mgmt."""
    # -- setup ----------------------------------------------------------------
    repos = _make_repos()
    _seed_black_cards(repos["black_cards"], n=10)
    _seed_white_cards(repos["white_cards"], n=60)
    bot = _build_mock_bot()

    def repo_factory(collection: str) -> InMemoryRepository:
        return repos[collection]

    # Create and persist player documents
    players: list[Player] = []
    player_ids: list[str] = []
    for i in range(NUM_PLAYERS):
        p = Player(repository=repo_factory("players"), repo_factory=repo_factory)
        p._bot = bot
        p._set_default_values()
        p._document["guild"] = GUILD_ID
        p._document["user"] = 1000 + i
        p._document["channel"] = 2000 + i
        await p.save()
        players.append(p)
        player_ids.append(p.document_id)

    # Create and persist game document
    game = Game(repository=repo_factory("games"), repo_factory=repo_factory)
    game._bot = bot
    game._set_default_values()
    game._document["guild"] = GUILD_ID
    game._document["board"] = BOARD_CHANNEL_ID
    game._document["players"] = list(player_ids)
    game._document["playing"] = True
    await game.save()

    drawn_black_cards: list[str] = []

    # -- play rounds ----------------------------------------------------------
    for round_num in range(NUM_ROUNDS):
        # 1. Pick a tsar
        await game.set_random_tsar()
        tsar_id = game.tsar_id
        assert tsar_id in player_ids

        # Reload the tsar player object
        tsar_player = await Player.create(bot, repo_factory, tsar_id)

        # 2. Draw a black card
        await game.draw_black_card()
        current_bc_id = game.black_cards_id[-1]
        drawn_black_cards.append(current_bc_id)

        # 3 & 4. Non-tsar players draw white cards and submit answers
        non_tsar_players: list[Player] = []
        for pid in player_ids:
            if pid == tsar_id:
                continue
            player = await Player.create(bot, repo_factory, pid)
            await player.draw_white_cards(game.white_cards_id or [])
            assert len(player.white_cards_id) == 7

            # Submit the first card as the answer (pick = 1)
            await player.add_answers([1])
            assert len(player.answers_id) == 1
            assert len(player.white_cards_id) == 6
            non_tsar_players.append(player)

        # 5. Send answers (formats proposals, shuffles, stores results)
        await game.send_answers()
        assert len(game._document["results"]) == NUM_PLAYERS - 1

        # 6. Tsar picks a winner (1-based index)
        tsar_player = await Player.create(bot, repo_factory, tsar_id)
        tsar_player.tsar_choice = 1
        await tsar_player.save()

        # 7. Select winner — awards 1 point, sets new tsar
        await game.select_winner()

    # -- assertions -----------------------------------------------------------

    # Total score across all players must equal the number of rounds
    total_score = 0
    for pid in player_ids:
        p = await Player.create(bot, repo_factory, pid)
        total_score += p.score or 0
    assert total_score == NUM_ROUNDS, (
        f"Expected total score {NUM_ROUNDS}, got {total_score}"
    )

    # All drawn black cards must be unique (no repeated draws)
    assert len(drawn_black_cards) == len(set(drawn_black_cards)), (
        "Black cards were repeated across rounds"
    )

    # Each non-tsar player's hand should still be managed correctly:
    # after drawing 7 and playing 1 each round, they re-draw to 7 next round
    for pid in player_ids:
        p = await Player.create(bot, repo_factory, pid)
        hand_size = len(p.white_cards_id or [])
        # Players who were tsar in the last round have cards from earlier
        # rounds; non-tsar players have 6 (drew 7 − played 1).
        # Either way the hand size should be <= 7.
        assert hand_size <= 7, f"Player {pid} hand too large: {hand_size}"


async def test_scores_accumulate_per_winner():
    """Winners accumulate points; non-winners stay at 0 (deterministic)."""
    repos = _make_repos()
    _seed_black_cards(repos["black_cards"], n=10)
    _seed_white_cards(repos["white_cards"], n=60)
    bot = _build_mock_bot()

    def repo_factory(collection: str) -> InMemoryRepository:
        return repos[collection]

    # Create players
    player_ids: list[str] = []
    for i in range(NUM_PLAYERS):
        p = Player(repository=repo_factory("players"), repo_factory=repo_factory)
        p._bot = bot
        p._set_default_values()
        p._document["guild"] = GUILD_ID
        p._document["user"] = 1000 + i
        p._document["channel"] = 2000 + i
        await p.save()
        player_ids.append(p.document_id)

    # Create game
    game = Game(repository=repo_factory("games"), repo_factory=repo_factory)
    game._bot = bot
    game._set_default_values()
    game._document["guild"] = GUILD_ID
    game._document["board"] = BOARD_CHANNEL_ID
    game._document["players"] = list(player_ids)
    game._document["playing"] = True
    await game.save()

    # Force player 0 as tsar so player at results[0] wins consistently
    game._document["tsar"] = player_ids[0]
    await game.save()

    # Play one round — the winner is whoever lands at index 0 in results
    await game.draw_black_card()
    for pid in player_ids:
        if pid == player_ids[0]:
            continue
        player = await Player.create(bot, repo_factory, pid)
        await player.draw_white_cards(game.white_cards_id or [])
        await player.add_answers([1])

    await game.send_answers()

    tsar = await Player.create(bot, repo_factory, player_ids[0])
    tsar.tsar_choice = 1
    await tsar.save()
    await game.select_winner()

    # Exactly one player should have score == 1
    scores = []
    for pid in player_ids:
        p = await Player.create(bot, repo_factory, pid)
        scores.append(p.score or 0)
    assert sum(scores) == 1
    assert scores.count(1) == 1


async def test_black_cards_unique_across_rounds():
    """The game must never draw the same black card twice."""
    repos = _make_repos()
    _seed_black_cards(repos["black_cards"], n=10)
    _seed_white_cards(repos["white_cards"], n=60)
    bot = _build_mock_bot()

    def repo_factory(collection: str) -> InMemoryRepository:
        return repos[collection]

    player_ids: list[str] = []
    for i in range(NUM_PLAYERS):
        p = Player(repository=repo_factory("players"), repo_factory=repo_factory)
        p._bot = bot
        p._set_default_values()
        p._document["guild"] = GUILD_ID
        p._document["user"] = 1000 + i
        p._document["channel"] = 2000 + i
        await p.save()
        player_ids.append(p.document_id)

    game = Game(repository=repo_factory("games"), repo_factory=repo_factory)
    game._bot = bot
    game._set_default_values()
    game._document["guild"] = GUILD_ID
    game._document["board"] = BOARD_CHANNEL_ID
    game._document["players"] = list(player_ids)
    game._document["playing"] = True
    await game.save()

    for _ in range(NUM_ROUNDS):
        game._document["tsar"] = player_ids[0]
        await game.save()
        await game.draw_black_card()

        for pid in player_ids[1:]:
            player = await Player.create(bot, repo_factory, pid)
            await player.draw_white_cards(game.white_cards_id or [])
            await player.add_answers([1])

        await game.send_answers()
        tsar = await Player.create(bot, repo_factory, player_ids[0])
        tsar.tsar_choice = 1
        await tsar.save()
        await game.select_winner()

    # All drawn black cards should be unique
    bc_ids = game.black_cards_id
    assert len(bc_ids) == NUM_ROUNDS
    assert len(set(bc_ids)) == NUM_ROUNDS


async def test_hand_management_draw_play_redraw():
    """Players draw to 7 cards, play some, then draw back to 7."""
    repos = _make_repos()
    _seed_black_cards(repos["black_cards"], n=10)
    _seed_white_cards(repos["white_cards"], n=60)
    bot = _build_mock_bot()

    def repo_factory(collection: str) -> InMemoryRepository:
        return repos[collection]

    p = Player(repository=repo_factory("players"), repo_factory=repo_factory)
    p._bot = bot
    p._set_default_values()
    p._document["guild"] = GUILD_ID
    p._document["user"] = 1000
    p._document["channel"] = 2000
    await p.save()

    # First draw — hand goes from 0 → 7
    await p.draw_white_cards([])
    assert len(p.white_cards_id) == 7

    # Play two cards (indices 1 and 2, 1-based)
    await p.add_answers([1, 2])
    assert len(p.white_cards_id) == 5
    assert len(p.answers_id) == 2

    # The played cards should no longer be in hand
    for aid in p.answers_id:
        assert aid not in p.white_cards_id

    # Clear answers and redraw
    await p.delete_answers()
    await p.draw_white_cards([])
    assert len(p.white_cards_id) == 7
