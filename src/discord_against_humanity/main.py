"""Composition root and command-line entry point.

This is the only module that knows every concrete adapter: it reads the
settings, builds the adapters and hands them to the application layer.
"""

import argparse
import asyncio
import logging
import signal
import sys
from collections.abc import Sequence

from valkey.asyncio import Valkey

from discord_against_humanity.adapters.cah_json import DEFAULT_SOURCE, load_source, parse_cards
from discord_against_humanity.adapters.discord.bot import CardsBot
from discord_against_humanity.adapters.valkey import ValkeyCardStore, ValkeyGameRepository
from discord_against_humanity.application.ports import GameNotifier
from discord_against_humanity.application.seeding import seed_cards
from discord_against_humanity.application.service import GameService
from discord_against_humanity.config import Settings

logger = logging.getLogger("discord_against_humanity")


def configure_logging(level: str) -> None:
    """Log to stdout only: the container filesystem is read-only."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        stream=sys.stdout,
        force=True,
    )
    # discord.py is chatty at DEBUG; keep it at INFO unless asked otherwise.
    logging.getLogger("discord").setLevel(max(logging.INFO, logging.getLevelNamesMapping()[level]))


def _valkey(settings: Settings) -> Valkey:
    return Valkey(
        host=settings.valkey_host,
        port=settings.valkey_port,
        db=settings.valkey_db,
        password=settings.valkey_password,
        decode_responses=True,
    )


async def run_bot(settings: Settings) -> int:
    if not settings.discord_token:
        logger.critical("DISCORD_TOKEN is not set")
        return 1

    client = _valkey(settings)
    await client.ping()
    store = ValkeyCardStore(client)
    black, white = await store.count()
    if not black or not white:
        logger.warning("The card catalog is empty: run the `seed` command first")

    def build_service(notifier: GameNotifier) -> GameService:
        return GameService(ValkeyGameRepository(client), store, notifier)

    bot = CardsBot(build_service)
    # Kubernetes stops pods with SIGTERM: log out cleanly instead of dying.
    shutdown: set[asyncio.Task[None]] = set()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: shutdown.add(loop.create_task(bot.close())))
    try:
        async with bot:
            await bot.start(settings.discord_token)
    finally:
        await client.aclose()
    return 0


async def run_seed(settings: Settings, source: str, *, force: bool, official_only: bool) -> int:
    logger.info("Loading cards from %s", source)
    black, white = parse_cards(load_source(source), official_only=official_only)
    client = _valkey(settings)
    try:
        await seed_cards(ValkeyCardStore(client), black, white, force=force)
    finally:
        await client.aclose()
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="discord-against-humanity", description=__doc__)
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("run", help="run the bot (default)")
    seed = commands.add_parser("seed", help="load the card catalog into Valkey")
    seed.add_argument(
        "source",
        nargs="?",
        help="path or URL of a JSON Against Humanity export "
        "(default: $CARDS_SOURCE, else the full public catalog)",
    )
    seed.add_argument("--force", action="store_true", help="replace an existing catalog")
    seed.add_argument("--official-only", action="store_true", help="only keep official packs")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    if args.command == "seed":
        source = args.source or settings.cards_source or DEFAULT_SOURCE
        return asyncio.run(
            run_seed(settings, source, force=args.force, official_only=args.official_only)
        )
    return asyncio.run(run_bot(settings))
