"""Valkey adapters against a real server (Testcontainers, needs Docker)."""

from collections.abc import AsyncIterator, Iterator
from random import Random

import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy
from valkey.asyncio import Valkey

from discord_against_humanity.adapters.valkey import ValkeyCardStore, ValkeyGameRepository
from discord_against_humanity.application.seeding import seed_cards
from discord_against_humanity.application.service import GameService
from discord_against_humanity.domain.errors import DeckExhaustedError
from discord_against_humanity.domain.game import Game, Phase
from tests.conftest import (
    BOARD,
    CATEGORY,
    GUILD,
    RecordingNotifier,
    make_black_cards,
    make_white_cards,
)

pytestmark = pytest.mark.integration

VALKEY_IMAGE = "valkey/valkey:9"


@pytest.fixture(scope="module")
def valkey_server() -> Iterator[tuple[str, int]]:
    container = (
        DockerContainer(VALKEY_IMAGE)
        .with_exposed_ports(6379)
        .waiting_for(LogMessageWaitStrategy("Ready to accept connections"))
    )
    with container:
        yield container.get_container_host_ip(), int(container.get_exposed_port(6379))


@pytest.fixture
async def client(valkey_server: tuple[str, int]) -> AsyncIterator[Valkey]:
    host, port = valkey_server
    valkey = Valkey(host=host, port=port, decode_responses=True)
    await valkey.flushdb()
    yield valkey
    await valkey.aclose()


@pytest.fixture
async def store(client: Valkey) -> ValkeyCardStore:
    store = ValkeyCardStore(client)
    await store.add(make_black_cards(), make_white_cards())
    return store


async def test_seed_is_idempotent(client: Valkey) -> None:
    store = ValkeyCardStore(client)
    assert await seed_cards(store, make_black_cards(), make_white_cards())
    assert not await seed_cards(store, make_black_cards(5), make_white_cards(5))
    assert await store.count() == (20, 200)

    assert await seed_cards(store, make_black_cards(5), make_white_cards(5), force=True)
    assert await store.count() == (5, 5)
    assert await client.dbsize() == 2 + 5 + 5


async def test_draw_respects_exclusions(store: ValkeyCardStore) -> None:
    excluded = {f"w{i}" for i in range(190)}
    cards = await store.draw_white_cards(10, excluded)
    assert {card.id for card in cards} == {f"w{i}" for i in range(190, 200)}

    black = await store.draw_black_card({f"b{i}" for i in range(19)})
    assert black.id == "b19"
    assert black.text == "Question 19: _."


async def test_draw_reports_exhaustion(store: ValkeyCardStore) -> None:
    with pytest.raises(DeckExhaustedError):
        await store.draw_white_cards(11, {f"w{i}" for i in range(190)})
    with pytest.raises(DeckExhaustedError):
        await store.draw_black_card({f"b{i}" for i in range(20)})


async def test_game_repository_round_trip(client: Valkey) -> None:
    repo = ValkeyGameRepository(client)
    assert await repo.get(GUILD) is None
    game = Game(guild_id=GUILD, category_id=CATEGORY, board_id=BOARD)
    game.add_player(1, channel_id=10)
    await repo.save(game)
    assert await repo.get(GUILD) == game
    await repo.delete(GUILD)
    assert await repo.get(GUILD) is None


async def test_full_game_on_valkey(client: Valkey, store: ValkeyCardStore) -> None:
    service = GameService(ValkeyGameRepository(client), store, RecordingNotifier(), Random(1))
    await service.create(GUILD, CATEGORY, BOARD)
    for uid in (1, 2, 3):
        await service.join(GUILD, uid, channel_id=100 + uid)
    await service.start(GUILD, points=1)

    game = await service.get(GUILD)
    assert game.round is not None
    for uid in game.round.participants:
        await service.submit_answers(GUILD, uid, [1])
    assert (await service.get(GUILD)).phase is Phase.JUDGING
    await service.pick_winner(GUILD, game.round.czar_id, 1)

    game = await service.get(GUILD)
    assert not game.started
    assert game.scoreboard()[0].score == 1
