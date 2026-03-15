"""Ports — abstract interfaces for the hexagonal architecture."""

from discord_against_humanity.ports.repository import (
    DocumentNotFoundError,
    Repository,
)

__all__ = [
    "DocumentNotFoundError",
    "Repository",
]
