"""Shared fixtures for Discord Against Humanity tests."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock
from uuid import uuid4

import pytest

from discord_against_humanity.ports.repository import Repository


@pytest.fixture
def mock_valkey_client():
    """Create a mock async Valkey client.

    The Valkey client is used via get/set/sadd/srandmember/etc.,
    so we mock the relevant methods.
    """
    client = MagicMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock()
    client.delete = AsyncMock()
    client.exists = AsyncMock(return_value=True)
    client.sadd = AsyncMock()
    client.srem = AsyncMock()
    client.srandmember = AsyncMock(return_value=None)
    client.scard = AsyncMock(return_value=0)
    return client


def _create_mock_repo():
    """Build a fresh mock Repository."""
    repo = MagicMock(spec=Repository)
    repo.find_by_id = AsyncMock(return_value=None)
    repo.find_one = AsyncMock(return_value=None)
    repo.insert = AsyncMock(return_value=str(uuid4()))
    repo.replace = AsyncMock(return_value={})
    repo.delete_by_id = AsyncMock()
    repo.random_member = AsyncMock(return_value=None)
    repo.count = AsyncMock(return_value=0)
    return repo


@pytest.fixture
def mock_repo():
    """Create a mock Repository."""
    return _create_mock_repo()


@pytest.fixture
def mock_repo_factory():
    """Create a mock RepositoryFactory.

    Returns the same mock Repository for any collection name
    so tests can inspect it easily.
    """
    repo = _create_mock_repo()
    factory = MagicMock(side_effect=lambda _collection: repo)
    factory._repo = repo  # expose for test assertions
    return factory


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
def sample_doc_id():
    """Return a sample document ID for testing."""
    return str(uuid4())


@pytest.fixture
def sample_doc_ids():
    """Return a list of sample document IDs for testing."""
    return [str(uuid4()) for _ in range(5)]
