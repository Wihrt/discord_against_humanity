"""Use case: load the card catalog."""

import logging
from collections.abc import Sequence

from discord_against_humanity.application.ports import CardCatalog
from discord_against_humanity.domain.cards import BlackCard, WhiteCard

logger = logging.getLogger(__name__)


async def seed_cards(
    catalog: CardCatalog,
    black: Sequence[BlackCard],
    white: Sequence[WhiteCard],
    *,
    force: bool = False,
) -> bool:
    """Store the given cards unless the catalog is already populated.

    Args:
        catalog: Where the cards are stored.
        black: Question cards to store.
        white: Answer cards to store.
        force: Replace the existing catalog instead of skipping.

    Returns:
        True if cards were written.
    """
    existing_black, existing_white = await catalog.count()
    if existing_black and existing_white and not force:
        logger.info(
            "Catalog already holds %d black / %d white cards, skipping",
            existing_black,
            existing_white,
        )
        return False
    if force:
        await catalog.clear()
    await catalog.add(black, white)
    logger.info("Seeded %d black / %d white cards", len(black), len(white))
    return True
