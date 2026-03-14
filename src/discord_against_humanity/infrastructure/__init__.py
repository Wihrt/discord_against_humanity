"""Infrastructure layer for database access."""

from discord_against_humanity.infrastructure.mongo import (
    DocumentNotFoundError,
    MongoDocument,
    MongoRepository,
    Repository,
)

__all__ = [
    "DocumentNotFoundError",
    "MongoDocument",
    "MongoRepository",
    "Repository",
]
