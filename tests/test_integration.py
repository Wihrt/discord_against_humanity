"""Integration tests using Testcontainers with a real MongoDB instance.

These tests verify that the repository pattern and domain models work
correctly against an actual MongoDB server seeded with card data.
They are automatically skipped when Docker is not available.
"""

import asyncio

import pytest
from bson.objectid import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from discord_against_humanity.infrastructure.mongo import (
    DocumentNotFoundError,
    MongoRepository,
)

# ---------------------------------------------------------------------------
# Testcontainers fixture
# ---------------------------------------------------------------------------

_can_use_docker = True
try:
    from testcontainers.mongodb import MongoDbContainer  # type: ignore[import-untyped]
except ImportError:
    _can_use_docker = False

pytestmark = pytest.mark.skipif(
    not _can_use_docker,
    reason="testcontainers[mongodb] not installed",
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
def mongo_container():
    """Start a MongoDB container for the duration of the test module."""
    with MongoDbContainer("mongo:8") as container:
        yield container


@pytest.fixture
def motor_client(mongo_container):  # type: ignore[no-untyped-def]
    """Create an async Motor client connected to the test container."""
    connection_url = mongo_container.get_connection_url()
    client: AsyncIOMotorClient = AsyncIOMotorClient(connection_url)  # type: ignore[type-arg]
    yield client
    client.close()


@pytest.fixture
def repository(motor_client):  # type: ignore[no-untyped-def]
    """Create a MongoRepository using the test container."""
    return MongoRepository(
        motor_client, "test_db", "test_collection"
    )


@pytest.fixture
async def seeded_client(motor_client):  # type: ignore[no-untyped-def]
    """Seed the ``cards_against_humanity`` database with card data.

    Inserts black and white cards into dedicated collections,
    then cleans them up after the test.
    """
    db = motor_client["cards_against_humanity"]

    black_col = db["black_cards"]
    white_col = db["white_cards"]

    await black_col.insert_many(
        [dict(card) for card in SEED_BLACK_CARDS]
    )
    await white_col.insert_many(
        [dict(card) for card in SEED_WHITE_CARDS]
    )

    yield motor_client

    await black_col.drop()
    await white_col.drop()
    await db["games"].drop()
    await db["players"].drop()


# ---------------------------------------------------------------------------
# Repository integration tests
# ---------------------------------------------------------------------------


class TestMongoRepositoryIntegration:
    """Integration tests for MongoRepository with a real MongoDB."""

    async def test_insert_and_find_by_id(self, repository):
        """Insert a document and retrieve it by ObjectId."""
        doc = {"name": "test_card", "text": "Hello world"}
        inserted_id = await repository.insert(doc)

        assert isinstance(inserted_id, ObjectId)
        result = await repository.find_by_id(inserted_id)
        assert result is not None
        assert result["name"] == "test_card"
        assert result["text"] == "Hello world"

    async def test_find_one(self, repository):
        """Find a document by query."""
        doc = {"guild": 42, "playing": True}
        await repository.insert(doc)

        result = await repository.find_one({"guild": 42})
        assert result is not None
        assert result["guild"] == 42
        assert result["playing"] is True

    async def test_find_one_returns_none_when_missing(self, repository):
        """find_one returns None when no document matches."""
        result = await repository.find_one(
            {"nonexistent": "value"}
        )
        assert result is None

    async def test_find_by_id_returns_none_when_missing(
        self, repository
    ):
        """find_by_id returns None for a nonexistent ObjectId."""
        result = await repository.find_by_id(ObjectId())
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
            await repository.replace(ObjectId(), {"value": "nope"})

    async def test_delete_by_id(self, repository):
        """Delete a document and confirm it's gone."""
        doc = {"to_delete": True}
        inserted_id = await repository.insert(doc)

        await repository.delete_by_id(inserted_id)
        result = await repository.find_by_id(inserted_id)
        assert result is None

    async def test_aggregate(self, repository):
        """Run a simple aggregation pipeline."""
        await repository.insert({"category": "a", "score": 10})
        await repository.insert({"category": "a", "score": 20})
        await repository.insert({"category": "b", "score": 5})

        pipeline = [
            {"$match": {"category": "a"}},
            {
                "$group": {
                    "_id": "$category",
                    "total": {"$sum": "$score"},
                }
            },
        ]
        results = await repository.aggregate(pipeline)
        assert len(results) == 1
        assert results[0]["_id"] == "a"
        assert results[0]["total"] == 30


# ---------------------------------------------------------------------------
# MongoDocument integration tests
# ---------------------------------------------------------------------------


class TestMongoDocumentIntegration:
    """Integration tests for MongoDocument save/get/delete cycle."""

    async def test_save_get_delete_cycle(self, motor_client):
        """Full lifecycle: save, get, and delete a document."""
        from discord_against_humanity.infrastructure.mongo import (
            MongoDocument,
        )

        class TestDoc(MongoDocument):
            _DATABASE = "test_db"
            _COLLECTION = "lifecycle_test"

            @classmethod
            async def create(cls):  # type: ignore[override]
                raise NotImplementedError

        doc = TestDoc(motor_client)
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

    async def test_concurrent_saves_do_not_corrupt(
        self, motor_client
    ):
        """Concurrent saves to different documents don't interfere."""
        from discord_against_humanity.infrastructure.mongo import (
            MongoDocument,
        )

        class TestDoc(MongoDocument):
            _DATABASE = "test_db"
            _COLLECTION = "concurrent_test"

            @classmethod
            async def create(cls):  # type: ignore[override]
                raise NotImplementedError

        doc_a = TestDoc(motor_client)
        doc_a._document = {"name": "A"}
        doc_b = TestDoc(motor_client)
        doc_b._document = {"name": "B"}

        await asyncio.gather(doc_a.save(), doc_b.save())

        assert doc_a.document_id is not None
        assert doc_b.document_id is not None
        assert doc_a.document_id != doc_b.document_id

        # Verify each document has correct data
        await doc_a.get(doc_a.document_id)
        await doc_b.get(doc_b.document_id)
        assert doc_a._document["name"] == "A"
        assert doc_b._document["name"] == "B"


# ---------------------------------------------------------------------------
# Card domain model integration tests (seeded database)
# ---------------------------------------------------------------------------


class TestBlackCardIntegration:
    """Integration tests for MongoBlackCard against a seeded database."""

    async def test_create_and_load_by_id(self, seeded_client):
        """Load a black card by ObjectId from the seeded collection."""
        from discord_against_humanity.domain.cards import (
            MongoBlackCard,
        )

        repo = MongoRepository(
            seeded_client,
            "cards_against_humanity",
            "black_cards",
        )
        results = await repo.aggregate(
            [{"$sample": {"size": 1}}]
        )
        card_id = results[0]["_id"]

        card = await MongoBlackCard.create(seeded_client, card_id)
        assert card.document_id == card_id
        assert card.text is not None
        assert len(card.text) > 0
        assert card.pick >= 1

    async def test_pick_value_matches_seed(self, seeded_client):
        """Verify pick values are preserved from seed data."""
        from discord_against_humanity.domain.cards import (
            MongoBlackCard,
        )

        repo = MongoRepository(
            seeded_client,
            "cards_against_humanity",
            "black_cards",
        )
        # Find the "pick 3" card
        doc = await repo.find_one({"pick": 3})
        assert doc is not None

        card = await MongoBlackCard.create(
            seeded_client, doc["_id"]
        )
        assert card.pick == 3

    async def test_text_with_underscore_formats_blanks(
        self, seeded_client
    ):
        """Black card text with underscores renders as bold blanks."""
        from discord_against_humanity.domain.cards import (
            MongoBlackCard,
        )

        repo = MongoRepository(
            seeded_client,
            "cards_against_humanity",
            "black_cards",
        )
        doc = await repo.find_one(
            {"text": {"$regex": "_"}}
        )
        assert doc is not None

        card = await MongoBlackCard.create(
            seeded_client, doc["_id"]
        )
        assert card.text is not None
        assert "_" not in card.text
        assert "{}" in card.text

    async def test_seeded_collection_count(self, seeded_client):
        """Verify the seeded collection has the expected number of cards."""
        repo = MongoRepository(
            seeded_client,
            "cards_against_humanity",
            "black_cards",
        )
        results = await repo.aggregate(
            [{"$count": "total"}]
        )
        assert results[0]["total"] == len(SEED_BLACK_CARDS)


class TestWhiteCardIntegration:
    """Integration tests for MongoWhiteCard against a seeded database."""

    async def test_create_and_load_by_id(self, seeded_client):
        """Load a white card by ObjectId from the seeded collection."""
        from discord_against_humanity.domain.cards import (
            MongoWhiteCard,
        )

        repo = MongoRepository(
            seeded_client,
            "cards_against_humanity",
            "white_cards",
        )
        results = await repo.aggregate(
            [{"$sample": {"size": 1}}]
        )
        card_id = results[0]["_id"]

        card = await MongoWhiteCard.create(seeded_client, card_id)
        assert card.document_id == card_id
        assert card.text is not None
        assert len(card.text) > 0

    async def test_seeded_collection_count(self, seeded_client):
        """Verify the seeded collection has the expected number of cards."""
        repo = MongoRepository(
            seeded_client,
            "cards_against_humanity",
            "white_cards",
        )
        results = await repo.aggregate(
            [{"$count": "total"}]
        )
        assert results[0]["total"] == len(SEED_WHITE_CARDS)

    async def test_text_html_is_converted(self, seeded_client):
        """White card text is converted from HTML to plain text."""
        from discord_against_humanity.domain.cards import (
            MongoWhiteCard,
        )

        # Insert a card with HTML content
        db = seeded_client["cards_against_humanity"]
        result = await db["white_cards"].insert_one(
            {"text": "<b>Bold answer</b>"}
        )
        card = await MongoWhiteCard.create(
            seeded_client, result.inserted_id
        )
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

        from discord_against_humanity.domain.game import MongoGame

        mock_bot = MagicMock()
        game = MongoGame(seeded_client)
        game._bot = mock_bot
        game._set_default_values()
        await game.save()

        embed = await game.draw_black_card()

        assert len(game.black_cards_id) == 1  # type: ignore[arg-type]
        assert embed is not None
        # Verify the drawn card exists in the database
        from discord_against_humanity.domain.cards import (
            MongoBlackCard,
        )

        card = await MongoBlackCard.create(
            seeded_client, game.black_cards_id[0]  # type: ignore[index]
        )
        assert card.text is not None

    async def test_draw_multiple_unique_black_cards(
        self, seeded_client
    ):
        """Drawing multiple black cards yields unique cards each time."""
        from unittest.mock import MagicMock

        from discord_against_humanity.domain.game import MongoGame

        mock_bot = MagicMock()
        game = MongoGame(seeded_client)
        game._bot = mock_bot
        game._set_default_values()
        await game.save()

        for _ in range(5):
            await game.draw_black_card()

        assert len(game.black_cards_id) == 5  # type: ignore[arg-type]
        unique_ids = set(game.black_cards_id)  # type: ignore[arg-type]
        assert len(unique_ids) == 5

    async def test_sample_random_white_cards(self, seeded_client):
        """$sample aggregation draws random white cards from the deck."""
        repo = MongoRepository(
            seeded_client,
            "cards_against_humanity",
            "white_cards",
        )
        results = await repo.aggregate(
            [{"$sample": {"size": 7}}]
        )
        assert len(results) == 7
        ids = [r["_id"] for r in results]
        # All drawn cards should have valid ObjectIds
        assert all(isinstance(i, ObjectId) for i in ids)
