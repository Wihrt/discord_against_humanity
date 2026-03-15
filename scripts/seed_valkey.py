#!/usr/bin/env python3
"""Seed a Valkey database with Cards Against Humanity card data.

This script is designed to run as an init container.  It waits for
Valkey to become reachable, checks whether seed data already exists,
and inserts cards from JSON files if not.

Usage::

    VALKEY_HOST=valkey VALKEY_PORT=6379 python seed_valkey.py
"""

from __future__ import annotations

import json
import logging
import sys
import time
from os import environ
from pathlib import Path
from uuid import uuid4

import valkey

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("seed")

SEED_DIR = Path(environ.get("SEED_DIR", "/app/seed"))
MAX_RETRIES = 30
RETRY_DELAY = 2


def wait_for_valkey(client: valkey.Valkey) -> None:
    """Block until Valkey is reachable, retrying on failure."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client.ping()
            logger.info("Valkey is ready (attempt %d)", attempt)
            return
        except valkey.ConnectionError:
            logger.info(
                "Waiting for Valkey… (attempt %d/%d)",
                attempt,
                MAX_RETRIES,
            )
            time.sleep(RETRY_DELAY)
    logger.error("Could not connect to Valkey after %d attempts", MAX_RETRIES)
    sys.exit(1)


def seed_collection(
    client: valkey.Valkey,
    collection: str,
    data: list[dict],
) -> None:
    """Insert documents into a Valkey collection.

    Each document is stored as a JSON string at ``{collection}:{id}``,
    and the ID is added to the ``{collection}:ids`` set.

    Args:
        client: Synchronous Valkey client.
        collection: The collection name (key prefix).
        data: List of document dicts to insert.
    """
    ids_key = f"{collection}:ids"
    pipe = client.pipeline()
    for doc in data:
        doc_id = str(uuid4())
        doc_data = {k: v for k, v in doc.items() if k != "_id"}
        pipe.set(f"{collection}:{doc_id}", json.dumps(doc_data))
        pipe.sadd(ids_key, doc_id)
    pipe.execute()
    logger.info("Inserted %d documents into '%s'", len(data), collection)


def main() -> None:
    """Connect to Valkey, check for existing data, and seed if needed."""
    host = environ.get("VALKEY_HOST", "localhost")
    port = int(environ.get("VALKEY_PORT", "6379"))

    client = valkey.Valkey(host=host, port=port, decode_responses=True)
    wait_for_valkey(client)

    # Check if data is already seeded
    if client.scard("black_cards:ids") > 0:
        logger.info("Seed data already exists — skipping.")
        client.close()
        return

    # Load and insert black cards
    black_path = SEED_DIR / "black_cards.json"
    if black_path.exists():
        with open(black_path, encoding="utf-8") as fh:
            black_cards = json.load(fh)
        seed_collection(client, "black_cards", black_cards)
    else:
        logger.warning("No black_cards.json found at %s", black_path)

    # Load and insert white cards
    white_path = SEED_DIR / "white_cards.json"
    if white_path.exists():
        with open(white_path, encoding="utf-8") as fh:
            white_cards = json.load(fh)
        seed_collection(client, "white_cards", white_cards)
    else:
        logger.warning("No white_cards.json found at %s", white_path)

    logger.info("Seeding complete.")
    client.close()


if __name__ == "__main__":
    main()
