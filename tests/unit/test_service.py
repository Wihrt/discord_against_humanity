import asyncio

import pytest

from discord_against_humanity.adapters.memory import InMemoryCardStore, InMemoryGameRepository
from discord_against_humanity.application.service import GameService
from discord_against_humanity.domain.cards import BlackCard
from discord_against_humanity.domain.errors import (
    DeckExhaustedError,
    GameAlreadyExistsError,
    NoGameError,
    NotEnoughPlayersError,
)
from discord_against_humanity.domain.game import HAND_SIZE, Game, Phase
from tests.conftest import (
    BOARD,
    CATEGORY,
    GUILD,
    RecordingNotifier,
    make_black_cards,
    make_white_cards,
)


async def lobby(service: GameService, players: int = 3) -> None:
    await service.create(GUILD, CATEGORY, BOARD)
    for uid in range(1, players + 1):
        await service.join(GUILD, uid, channel_id=100 + uid)


async def play_round(service: GameService) -> Game:
    """Every participant plays their first card(s), then the czar picks #1."""
    game = await service.get(GUILD)
    assert game.round is not None
    pick = game.round.black_card.pick
    for uid in game.round.participants:
        await service.submit_answers(GUILD, uid, list(range(1, pick + 1)))
    await service.pick_winner(GUILD, game.round.czar_id, 1)
    return await service.get(GUILD)


async def test_create_and_delete(service: GameService) -> None:
    created = await service.create(GUILD, CATEGORY, BOARD)
    assert await service.find(GUILD) == created
    with pytest.raises(GameAlreadyExistsError):
        await service.create(GUILD, CATEGORY, BOARD)
    deleted = await service.delete(GUILD)
    assert deleted.board_id == BOARD
    assert await service.find(GUILD) is None
    with pytest.raises(NoGameError):
        await service.get(GUILD)


async def test_start_deals_cards_and_opens_a_round(
    service: GameService, notifier: RecordingNotifier
) -> None:
    await lobby(service)
    game = await service.start(GUILD, points=3)

    assert game.phase is Phase.ANSWERING
    assert all(len(p.hand) == HAND_SIZE for p in game.players.values())
    dealt = [card.id for p in game.players.values() for card in p.hand]
    assert len(dealt) == len(set(dealt)), "a card was dealt twice"
    assert notifier.names()[-2:] == ["game_started", "round_started"]


async def test_failed_start_leaves_the_game_untouched(
    games: InMemoryGameRepository, notifier: RecordingNotifier
) -> None:
    service = GameService(games, InMemoryCardStore(make_black_cards(), []), notifier)
    await lobby(service)
    with pytest.raises(DeckExhaustedError):
        await service.start(GUILD, points=3)
    game = await service.get(GUILD)
    assert not game.started
    assert all(not p.hand for p in game.players.values())


async def test_start_needs_players(service: GameService) -> None:
    await lobby(service, players=1)
    with pytest.raises(NotEnoughPlayersError):
        await service.start(GUILD, points=3)


async def test_full_game(service: GameService, notifier: RecordingNotifier) -> None:
    await lobby(service, players=4)
    await service.start(GUILD, points=2)

    rounds = 0
    game = await service.get(GUILD)
    while game.started:
        game = await play_round(service)
        rounds += 1
        assert rounds < 20, "the game never ends"
        if game.started:
            # Hands are refilled at the start of every round.
            assert all(len(p.hand) == HAND_SIZE for p in game.players.values())

    winner = game.scoreboard()[0]
    assert winner.score == 2
    assert notifier.events[-1] == ("game_over", winner.user_id)
    assert notifier.names().count("judging_started") == rounds
    assert len(game.used_black_cards) == rounds


async def test_card_czar_rotates(service: GameService) -> None:
    await lobby(service)
    game = await service.start(GUILD, points=5)
    assert game.round is not None
    order = list(game.players)
    first = order.index(game.round.czar_id)
    game = await play_round(service)
    assert game.round is not None
    assert game.round.czar_id == order[(first + 1) % len(order)]


async def test_house_rule_winner_becomes_czar(service: GameService) -> None:
    await lobby(service)
    await service.start(GUILD, points=5, winner_becomes_czar=True)
    game = await play_round(service)
    assert game.round is not None
    assert game.round.czar_id == game.scoreboard()[0].user_id


async def test_draw_two_pick_three_deals_extra_cards(
    games: InMemoryGameRepository, notifier: RecordingNotifier
) -> None:
    deck = InMemoryCardStore(make_black_cards(pick=3), make_white_cards())
    service = GameService(games, deck, notifier)
    await lobby(service)
    game = await service.start(GUILD, points=5)
    assert game.round is not None
    for uid, player in game.players.items():
        expected = HAND_SIZE if uid == game.round.czar_id else HAND_SIZE + 2
        assert len(player.hand) == expected

    # After playing 3 of their 12 cards, answerers are topped up to 10, plus
    # 2 again because the next card is also a "Draw 2, Pick 3".
    game = await play_round(service)
    assert game.round is not None
    czar_id = game.round.czar_id
    assert len(game.players[czar_id].hand) == HAND_SIZE
    assert all(len(p.hand) == HAND_SIZE + 2 for uid, p in game.players.items() if uid != czar_id)


async def test_unplayable_black_cards_are_skipped(
    games: InMemoryGameRepository, notifier: RecordingNotifier
) -> None:
    unplayable = [BlackCard(id=f"x{i}", text="Name ten things.", pick=10) for i in range(5)]
    deck = InMemoryCardStore([*unplayable, *make_black_cards(1)], make_white_cards())
    service = GameService(games, deck, notifier)
    await lobby(service)
    game = await service.start(GUILD, points=5)
    assert game.round is not None
    assert game.round.black_card.id == "b0"


async def test_stop(service: GameService, notifier: RecordingNotifier) -> None:
    await lobby(service)
    await service.start(GUILD, points=5)
    game = await service.stop(GUILD)
    assert not game.started
    assert notifier.events[-1] == ("game_stopped", "The game was stopped.")


async def test_czar_leaving_restarts_the_round(
    service: GameService, notifier: RecordingNotifier
) -> None:
    await lobby(service, players=4)
    game = await service.start(GUILD, points=5)
    assert game.round is not None
    old_czar = game.round.czar_id

    await service.leave(GUILD, old_czar)

    game = await service.get(GUILD)
    assert game.round is not None
    assert game.round.czar_id != old_czar
    assert notifier.names()[-3:] == ["player_left", "round_cancelled", "round_started"]


async def test_leaving_below_minimum_stops_the_game(
    service: GameService, notifier: RecordingNotifier
) -> None:
    await lobby(service, players=3)
    await service.start(GUILD, points=5)
    await service.leave(GUILD, 1)
    assert not (await service.get(GUILD)).started
    assert notifier.events[-1] == ("game_stopped", "Not enough players left.")


async def test_deck_running_out_stops_the_game(
    games: InMemoryGameRepository, notifier: RecordingNotifier
) -> None:
    deck = InMemoryCardStore(make_black_cards(count=1), make_white_cards())
    service = GameService(games, deck, notifier)
    await lobby(service)
    await service.start(GUILD, points=5)
    game = await play_round(service)
    assert not game.started
    assert notifier.events[-1] == ("game_stopped", "No cards left in the deck.")


async def test_concurrent_answers_are_all_kept(service: GameService) -> None:
    await lobby(service, players=6)
    game = await service.start(GUILD, points=5)
    assert game.round is not None
    await asyncio.gather(
        *(service.submit_answers(GUILD, uid, [1]) for uid in game.round.participants)
    )
    game = await service.get(GUILD)
    assert game.phase is Phase.JUDGING
    assert len(game.proposals()) == 5
