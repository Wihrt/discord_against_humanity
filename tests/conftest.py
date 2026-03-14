"""Shared fixtures for Discord Against Humanity tests."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest
from bson.objectid import ObjectId


@pytest.fixture
def mock_mongo_client():
    """Create a mock Motor async MongoDB client.

    The motor client is accessed as client[database][collection],
    so we mock nested __getitem__ calls to return an AsyncMock collection.
    """
    client = MagicMock()
    collection = AsyncMock()
    database = MagicMock()
    database.__getitem__ = MagicMock(return_value=collection)
    client.__getitem__ = MagicMock(return_value=database)
    return client


@pytest.fixture
def mock_collection(mock_mongo_client):
    """Return the mock collection from the mock client."""
    return mock_mongo_client["any_db"]["any_collection"]


@pytest.fixture
def mock_bot():
    """Create a mock Discord Bot."""
    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=None)
    return bot


@pytest.fixture
def mock_guild():
    """Create a mock Discord Guild."""
    from discord import Guild

    guild = MagicMock(spec=Guild)
    guild.id = 123456789
    guild.get_channel = MagicMock(return_value=None)
    guild.get_member = MagicMock(return_value=None)
    return guild


@pytest.fixture
def mock_member(mock_guild):
    """Create a mock Discord Member."""
    from discord import Member

    member = MagicMock(spec=Member)
    member.id = 987654321
    member.display_name = "TestPlayer"
    member.mention = "<@987654321>"
    # Guild property needs to be accessible
    type(member).guild = PropertyMock(return_value=mock_guild)
    return member


@pytest.fixture
def mock_text_channel():
    """Create a mock Discord TextChannel."""
    from discord import TextChannel

    channel = MagicMock(spec=TextChannel)
    channel.id = 111222333
    channel.send = AsyncMock()
    return channel


@pytest.fixture
def mock_category_channel():
    """Create a mock Discord CategoryChannel."""
    from discord import CategoryChannel

    category = MagicMock(spec=CategoryChannel)
    category.id = 444555666
    return category


@pytest.fixture
def sample_object_id():
    """Return a sample ObjectId for testing."""
    return ObjectId()


@pytest.fixture
def sample_object_ids():
    """Return a list of sample ObjectIds for testing."""
    return [ObjectId() for _ in range(5)]
