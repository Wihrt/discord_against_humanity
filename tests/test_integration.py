"""Integration tests using Testcontainers with a real Valkey instance.

These tests verify that the repository pattern and domain models work
correctly against an actual Valkey server seeded with card data.
They are automatically skipped when Docker is not available.
"""

import json

import pytest

from discord_against_humanity.adapters.valkey import (
    ValkeyRepository,
    create_repo_factory,
)
from discord_against_humanity.ports.repository import DocumentNotFoundError

# ---------------------------------------------------------------------------
# Testcontainers fixture
# ---------------------------------------------------------------------------

_can_use_docker = True
try:
    from testcontainers.core.container import DockerContainer
    from testcontainers.core.waiting_utils import wait_for_logs
except ImportError:
    _can_use_docker = False

pytestmark = pytest.mark.skipif(
    not _can_use_docker,
    reason="testcontainers not installed",
)

# ---------------------------------------------------------------------------
# Seed data — minimal Cards Against Humanity card sets
# ---------------------------------------------------------------------------

SEED_BLACK_CARDS = [
    {"text": "Why can't I sleep at night?", "pick": 1},
    {"text": "I got 99 problems but _ ain't one.", "pick": 1},
    {"text": "What's a girl's best friend?", "pick": 1},
    {"text": "_ + _ = _.", "pick": 3},
    {"text": "In a world ravaged by _, our only solace is _.", "pick": 2},
    {"text": "What is Batman's guilty pleasure?", "pick": 1},
    {"text": "TSA guidelines now prohibit _ on airplanes.", "pick": 1},
    {"text": "What ended my last relationship?", "pick": 1},
    {"text": "What's the next Happy Meal toy?", "pick": 1},
    {"text": "Introducing the amazing superhero/sidekick duo! _ and _!", "pick": 2},
]

SEED_WHITE_CARDS = [
    {"text": "Flying sex snakes."},
    {"text": "A disappointing birthday party."},
    {"text": "Puppies!"},
    {"text": "A windmill full of corpses."},
    {"text": "Bees?"},
    {"text": "An asymmetric boob job."},
    {"text": "A salty surprise."},
    {"text": "Cards Against Humanity."},
    {"text": "Doing the right thing."},
    {"text": "Exactly what you'd expect."},
    {"text": "A snapping turtle biting the tip of your penis."},
    {"text": "The miracle of childbirth."},
    {"text": "A stray pube."},
    {"text": "One thousand Slim Jims."},
    {"text": "Being a motherfucking sorcerer."},
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def valkey_container():
    """Start a Valkey container for the duration of the test module."""
    container = DockerContainer("valkey/valkey:8")
    container.with_exposed_ports(6379)
    container.start()
    wait_for_logs(container, "Ready to accept connections")
    yield container
    container.stop()


@pytest.fixture
def valkey_client(valkey_container):
    """Create an async Valkey client connected to the test container."""
    import valkey.asyncio as aio_valkey

    host = valkey_container.get_container_host_ip()
    port = valkey_container.get_exposed_port(6379)
    client = aio_valkey.Valkey(
        host=host, port=int(port), decode_responses=True
    )
    yield client


@pytest.fixture
def repository(valkey_client):
    """Create a ValkeyRepository with a unique collection per test."""
    from uuid import uuid4

    return ValkeyRepository(
        valkey_client, f"test_collection_{uuid4().hex[:8]}"
    )


@pytest.fixture
async def seeded_client(valkey_client):
    """Seed the Valkey database with card data.

    Inserts black and white cards into dedicated collections,
    then cleans them up after the test.
    """
    from uuid import uuid4

    # Seed black cards
    for card in SEED_BLACK_CARDS:
        doc_id = str(uuid4())
        await valkey_client.set(
            f"black_cards:{doc_id}",
            json.dumps(card),
        )
        await valkey_client.sadd("black_cards:ids", doc_id)

    # Seed white cards
    for card in SEED_WHITE_CARDS:
        doc_id = str(uuid4())
        await valkey_client.set(
            f"white_cards:{doc_id}",
            json.dumps(card),
        )
        await valkey_client.sadd("white_cards:ids", doc_id)

    yield valkey_client

    # Cleanup
    await valkey_client.flushdb()


# ---------------------------------------------------------------------------
# Repository integration tests
# ---------------------------------------------------------------------------


class TestValkeyRepositoryIntegration:
    """Integration tests for ValkeyRepository with a real Valkey server."""

    async def test_insert_and_find_by_id(self, repository):
        """Insert a document and retrieve it by ID."""
        doc = {"name": "test_card", "text": "Hello world"}
        inserted_id = await repository.insert(doc)

        assert isinstance(inserted_id, str)
        result = await repository.find_by_id(inserted_id)
        assert result is not None
        assert result["name"] == "test_card"
        assert result["text"] == "Hello world"

    async def test_find_one_with_index(self, valkey_client):
        """Find a document by indexed query."""
        repo = ValkeyRepository(
            valkey_client, "indexed_test", index_fields=["guild"]
        )
        doc = {"guild": 42, "playing": True}
        await repo.insert(doc)

        result = await repo.find_one({"guild": 42})
        assert result is not None
        assert result["guild"] == 42
        assert result["playing"] is True

    async def test_find_one_returns_none_when_missing(self, valkey_client):
        """find_one returns None when no document matches."""
        repo = ValkeyRepository(
            valkey_client, "missing_test", index_fields=["nonexistent"]
        )
        result = await repo.find_one(
            {"nonexistent": "value"}
        )
        assert result is None

    async def test_find_by_id_returns_none_when_missing(
        self, repository
    ):
        """find_by_id returns None for a nonexistent ID."""
        result = await repository.find_by_id("nonexistent-id")
        assert result is None

    async def test_replace(self, repository):
        """Replace an existing document."""
        doc = {"value": "original"}
        inserted_id = await repository.insert(doc)

        updated = await repository.replace(
            inserted_id, {"value": "updated"}
        )
        assert updated["value"] == "updated"

        reloaded = await repository.find_by_id(inserted_id)
        assert reloaded is not None
        assert reloaded["value"] == "updated"

    async def test_replace_nonexistent_raises_error(self, repository):
        """Replace raises DocumentNotFoundError for missing docs."""
        with pytest.raises(DocumentNotFoundError):
            await repository.replace("nonexistent-id", {"value": "nope"})

    async def test_delete_by_id(self, repository):
        """Delete a document and confirm it's gone."""
        doc = {"to_delete": True}
        inserted_id = await repository.insert(doc)

        await repository.delete_by_id(inserted_id)
        result = await repository.find_by_id(inserted_id)
        assert result is None

    async def test_random_member(self, repository):
        """random_member returns a document from the collection."""
        await repository.insert({"value": "a"})
        await repository.insert({"value": "b"})

        result = await repository.random_member()
        assert result is not None
        assert result["value"] in ("a", "b")

    async def test_count(self, repository):
        """count returns the number of documents."""
        await repository.insert({"value": "x"})
        await repository.insert({"value": "y"})
        await repository.insert({"value": "z"})

        result = await repository.count()
        assert result >= 3


# ---------------------------------------------------------------------------
# Document integration tests
# ---------------------------------------------------------------------------


class TestDocumentIntegration:
    """Integration tests for Document save/get/delete cycle."""

    async def test_save_get_delete_cycle(self, valkey_client):
        """Full lifecycle: save, get, and delete a document."""
        from discord_against_humanity.domain.document import Document

        factory = create_repo_factory(valkey_client)

        class TestDoc(Document):
            _COLLECTION = "lifecycle_test"

            @classmethod
            async def create(cls):
                raise NotImplementedError

        doc = TestDoc(
            repository=factory("lifecycle_test"),
            repo_factory=factory,
        )
        doc._document = {"field": "value"}

        # Save (insert)
        await doc.save()
        assert doc.document_id is not None

        # Get (reload)
        original_id = doc.document_id
        doc._document = {}
        await doc.get(original_id)
        assert doc._document["field"] == "value"

        # Save (update)
        doc._document["field"] = "updated"
        await doc.save()
        await doc.get(original_id)
        assert doc._document["field"] == "updated"

        # Delete
        await doc.delete()
        doc._document = {}
        await doc.get(original_id)
        assert doc.document_id is None


# ---------------------------------------------------------------------------
# Card domain model integration tests (seeded database)
# ---------------------------------------------------------------------------


class TestBlackCardIntegration:
    """Integration tests for BlackCard against a seeded database."""

    async def test_create_and_load_by_id(self, seeded_client):
        """Load a black card by ID from the seeded collection."""
        from discord_against_humanity.domain.cards import (
            BlackCard,
        )

        factory = create_repo_factory(seeded_client)
        repo = ValkeyRepository(seeded_client, "black_cards")
        document = await repo.random_member()
        assert document is not None
        card_id = document["_id"]

        card = await BlackCard.create(factory, card_id)
        assert card.document_id == card_id
        assert card.text is not None
        assert len(card.text) > 0
        assert card.pick >= 1

    async def test_pick_value_matches_seed(self, seeded_client):
        """Verify pick values are preserved from seed data."""
        from discord_against_humanity.domain.cards import (
            BlackCard,
        )

        factory = create_repo_factory(seeded_client)

        # Find the "pick 3" card by iterating through all cards
        all_ids = await seeded_client.smembers("black_cards:ids")
        pick3_id = None
        for card_id in all_ids:
            data = await seeded_client.get(f"black_cards:{card_id}")
            doc = json.loads(data)
            if doc.get("pick") == 3:
                pick3_id = card_id
                break

        assert pick3_id is not None
        card = await BlackCard.create(factory, pick3_id)
        assert card.pick == 3

    async def test_text_with_underscore_formats_blanks(
        self, seeded_client
    ):
        """Black card text with underscores renders as bold blanks."""
        from discord_against_humanity.domain.cards import (
            BlackCard,
        )

        factory = create_repo_factory(seeded_client)

        # Find a card with underscore in text
        all_ids = await seeded_client.smembers("black_cards:ids")
        underscore_id = None
        for card_id in all_ids:
            data = await seeded_client.get(f"black_cards:{card_id}")
            doc = json.loads(data)
            if "_" in doc.get("text", ""):
                underscore_id = card_id
                break

        assert underscore_id is not None
        card = await BlackCard.create(factory, underscore_id)
        assert card.text is not None
        assert "_" not in card.text
        assert "{}" in card.text

    async def test_seeded_collection_count(self, seeded_client):
        """Verify the seeded collection has the expected number of cards."""
        repo = ValkeyRepository(seeded_client, "black_cards")
        count = await repo.count()
        assert count == len(SEED_BLACK_CARDS)


class TestWhiteCardIntegration:
    """Integration tests for WhiteCard against a seeded database."""

    async def test_create_and_load_by_id(self, seeded_client):
        """Load a white card by ID from the seeded collection."""
        from discord_against_humanity.domain.cards import (
            WhiteCard,
        )

        factory = create_repo_factory(seeded_client)
        repo = ValkeyRepository(seeded_client, "white_cards")
        document = await repo.random_member()
        assert document is not None
        card_id = document["_id"]

        card = await WhiteCard.create(factory, card_id)
        assert card.document_id == card_id
        assert card.text is not None
        assert len(card.text) > 0

    async def test_seeded_collection_count(self, seeded_client):
        """Verify the seeded collection has the expected number of cards."""
        repo = ValkeyRepository(seeded_client, "white_cards")
        count = await repo.count()
        assert count == len(SEED_WHITE_CARDS)

    async def test_text_html_is_converted(self, seeded_client):
        """White card text is converted from HTML to plain text."""
        from uuid import uuid4

        from discord_against_humanity.domain.cards import (
            WhiteCard,
        )

        factory = create_repo_factory(seeded_client)

        # Insert a card with HTML content
        doc_id = str(uuid4())
        await seeded_client.set(
            f"white_cards:{doc_id}",
            json.dumps({"text": "<b>Bold answer</b>"}),
        )
        await seeded_client.sadd("white_cards:ids", doc_id)

        card = await WhiteCard.create(factory, doc_id)
        assert card.text is not None
        assert "<b>" not in card.text
        assert "Bold answer" in card.text


# ---------------------------------------------------------------------------
# Game domain model integration tests (seeded database)
# ---------------------------------------------------------------------------


class TestGameCardDrawIntegration:
    """Integration tests for card-drawing logic against a seeded database."""

    async def test_draw_black_card_from_seeded_deck(
        self, seeded_client
    ):
        """draw_black_card retrieves a card from the seeded deck."""
        from unittest.mock import MagicMock

        from discord_against_humanity.domain.game import Game

        factory = create_repo_factory(seeded_client)
        mock_bot = MagicMock()
        game = Game(
            repository=factory("games"),
            repo_factory=factory,
        )
        game._bot = mock_bot
        game._set_default_values()
        await game.save()

        embed = await game.draw_black_card()

        assert len(game.black_cards_id) == 1
        assert embed is not None
        # Verify the drawn card exists in the database
        from discord_against_humanity.domain.cards import (
            BlackCard,
        )

        card = await BlackCard.create(
            factory, game.black_cards_id[0]
        )
        assert card.text is not None

    async def test_draw_multiple_unique_black_cards(
        self, seeded_client
    ):
        """Drawing multiple black cards yields unique cards each time."""
        from unittest.mock import MagicMock

        from discord_against_humanity.domain.game import Game

        factory = create_repo_factory(seeded_client)
        mock_bot = MagicMock()
        game = Game(
            repository=factory("games"),
            repo_factory=factory,
        )
        game._bot = mock_bot
        game._set_default_values()
        await game.save()

        for _ in range(5):
            await game.draw_black_card()

        assert len(game.black_cards_id) == 5
        unique_ids = set(game.black_cards_id)
        assert len(unique_ids) == 5

    async def test_sample_random_white_cards(self, seeded_client):
        """random_member draws random white cards from the deck."""
        repo = ValkeyRepository(seeded_client, "white_cards")
        results = []
        for _ in range(7):
            doc = await repo.random_member()
            assert doc is not None
            results.append(doc)

        assert len(results) == 7
        ids = [r["_id"] for r in results]
        # All drawn cards should have valid string IDs
        assert all(isinstance(i, str) for i in ids)
