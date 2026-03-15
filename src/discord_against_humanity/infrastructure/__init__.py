"""Infrastructure package — re-exports for backward compatibility."""

from discord_against_humanity.adapters.valkey import ValkeyRepository
from discord_against_humanity.domain.document import Document
from discord_against_humanity.ports.repository import (
    DocumentNotFoundError,
    Repository,
)

__all__ = [
    "DocumentNotFoundError",
    "Document",
    "Repository",
    "ValkeyRepository",
]
