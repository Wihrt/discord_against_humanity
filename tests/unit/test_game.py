from random import Random

import pytest

from discord_against_humanity.domain.cards import BlackCard, WhiteCard
from discord_against_humanity.domain.errors import (
    AlreadyPlayerError,
    GameAlreadyStartedError,
    GameNotStartedError,
    InvalidChoiceError,
    InvalidPointsError,
    NotAPlayerError,
    NotEnoughPlayersError,
    WrongPhaseError,
)
from discord_against_humanity.domain.game import HAND_SIZE, Game, Phase

QUESTION = BlackCard(id="q1", text="_ is my weakness.")
DOUBLE = BlackCard(id="q2", text="_ then _.", pick=2)


def hand(owner: int) -> list[WhiteCard]:
    return [WhiteCard(id=f"{owner}-{i}", text=f"Card {owner}-{i}") for i in range(HAND_SIZE)]


def started_game(
    players: int = 3, card: BlackCard = QUESTION, czar: int = 1, points: int = 2
) -> Game:
    game = Game(guild_id=1, category_id=2, board_id=3)
    for uid in range(1, players + 1):
        game.add_player(uid, channel_id=100 + uid)
        game.deal(uid, hand(uid))
    game.start(points=points)
    game.next_czar_id = czar
    game.begin_round(card, Random(0))
    return game


def everyone_answers(game: Game, rng: Random) -> None:
    assert game.round is not None
    for uid in game.round.participants:
        game.submit_answers(uid, list(range(1, game.round.black_card.pick + 1)), rng)


class TestLobby:
    def test_add_player_twice_is_refused(self) -> None:
        game = Game(guild_id=1, category_id=2, board_id=3)
        game.add_player(1, channel_id=10)
        with pytest.raises(AlreadyPlayerError):
            game.add_player(1, channel_id=11)

    def test_unknown_player(self) -> None:
        with pytest.raises(NotAPlayerError):
            Game(guild_id=1, category_id=2, board_id=3).player(42)

    def test_start_needs_enough_players(self) -> None:
        game = Game(guild_id=1, category_id=2, board_id=3)
        game.add_player(1, channel_id=10)
        with pytest.raises(NotEnoughPlayersError):
            game.start(points=5)

    @pytest.mark.parametrize("points", [0, 51])
    def test_start_validates_points(self, points: int) -> None:
        game = Game(guild_id=1, category_id=2, board_id=3)
        game.add_player(1, channel_id=10)
        game.add_player(2, channel_id=20)
        with pytest.raises(InvalidPointsError):
            game.start(points=points)

    def test_start_twice_is_refused(self) -> None:
        game = started_game()
        with pytest.raises(GameAlreadyStartedError):
            game.start(points=3)

    def test_start_resets_scores(self) -> None:
        game = Game(guild_id=1, category_id=2, board_id=3)
        game.add_player(1, channel_id=10).score = 4
        game.add_player(2, channel_id=20)
        game.add_player(3, channel_id=30)
        game.start(points=5)
        assert game.players[1].score == 0

    def test_cards_needed(self) -> None:
        game = Game(guild_id=1, category_id=2, board_id=3)
        game.add_player(1, channel_id=10)
        game.add_player(2, channel_id=20)
        game.deal(2, hand(2)[:5])
        assert game.cards_needed() == {1: HAND_SIZE, 2: HAND_SIZE - 5}

    def test_stop_requires_started_game(self) -> None:
        with pytest.raises(GameNotStartedError):
            Game(guild_id=1, category_id=2, board_id=3).stop()


class TestRound:
    def test_begin_round(self) -> None:
        game = started_game(czar=2)
        assert game.phase is Phase.ANSWERING
        assert game.round is not None
        assert game.round.czar_id == 2
        assert game.round.participants == [1, 3]
        assert QUESTION.id in game.used_black_cards

    def test_begin_round_picks_a_czar_when_none_is_set(self) -> None:
        game = Game(guild_id=1, category_id=2, board_id=3)
        for uid in (1, 2, 3):
            game.add_player(uid, channel_id=10 * uid)
        game.start(points=5)
        round_ = game.begin_round(QUESTION, Random(0))
        assert round_.czar_id in (1, 2, 3)

    def test_cannot_begin_two_rounds(self) -> None:
        game = started_game()
        with pytest.raises(WrongPhaseError):
            game.begin_round(QUESTION, Random(0))

    def test_answer_moves_cards_out_of_the_hand(self) -> None:
        game = started_game()
        card = game.players[2].hand[2]
        game.submit_answers(2, [3], Random(0))
        assert card not in game.players[2].hand
        assert game.round is not None
        assert game.round.answers[2] == [card]

    def test_multi_pick_keeps_choice_order(self) -> None:
        game = started_game(card=DOUBLE)
        first, second = game.players[2].hand[4], game.players[2].hand[1]
        game.submit_answers(2, [5, 2], Random(0))
        assert game.round is not None
        assert game.round.answers[2] == [first, second]
        assert len(game.players[2].hand) == HAND_SIZE - 2

    @pytest.mark.parametrize("choices", [[], [1, 2], [0], [HAND_SIZE + 1], [-1]])
    def test_invalid_choices(self, choices: list[int]) -> None:
        game = started_game()
        with pytest.raises(InvalidChoiceError):
            game.submit_answers(2, choices, Random(0))

    def test_same_card_twice(self) -> None:
        game = started_game(card=DOUBLE)
        with pytest.raises(InvalidChoiceError):
            game.submit_answers(2, [3, 3], Random(0))

    def test_czar_cannot_answer(self) -> None:
        game = started_game(czar=1)
        with pytest.raises(WrongPhaseError):
            game.submit_answers(1, [1], Random(0))

    def test_answer_only_once(self) -> None:
        game = started_game()
        game.submit_answers(2, [1], Random(0))
        with pytest.raises(WrongPhaseError):
            game.submit_answers(2, [1], Random(0))

    def test_late_joiner_waits_for_next_round(self) -> None:
        game = started_game()
        game.add_player(9, channel_id=109)
        game.deal(9, hand(9))
        with pytest.raises(WrongPhaseError):
            game.submit_answers(9, [1], Random(0))

    def test_last_answer_starts_judging(self) -> None:
        game = started_game()
        rng = Random(0)
        assert game.submit_answers(2, [1], rng) is False
        assert game.submit_answers(3, [1], rng) is True
        assert game.phase is Phase.JUDGING
        assert sorted(uid for uid, _ in game.proposals()) == [2, 3]

    def test_cannot_judge_while_answering(self) -> None:
        game = started_game()
        with pytest.raises(WrongPhaseError):
            game.pick_winner(1, 1)

    def test_cannot_answer_while_judging(self) -> None:
        game = started_game()
        everyone_answers(game, Random(0))
        with pytest.raises(WrongPhaseError):
            game.submit_answers(2, [1], Random(0))


class TestJudging:
    def test_only_czar_picks(self) -> None:
        game = started_game(czar=1)
        everyone_answers(game, Random(0))
        with pytest.raises(WrongPhaseError):
            game.pick_winner(2, 1)

    @pytest.mark.parametrize("choice", [0, 3])
    def test_choice_must_match_a_proposal(self, choice: int) -> None:
        game = started_game(czar=1)
        everyone_answers(game, Random(0))
        with pytest.raises(InvalidChoiceError):
            game.pick_winner(1, choice)

    def test_winner_scores_and_judges_next(self) -> None:
        game = started_game(czar=1)
        everyone_answers(game, Random(0))
        winner_id, cards = game.proposals()[0]
        result = game.pick_winner(1, 1)

        assert result.winner_id == winner_id
        assert list(result.answers) == cards
        assert not result.game_over
        assert game.players[winner_id].score == 1
        assert game.next_czar_id == winner_id
        assert game.phase is Phase.LOBBY
        assert {card.id for card in cards} <= game.discarded_white_cards

    def test_reaching_the_target_ends_the_game(self) -> None:
        game = started_game(czar=1)
        everyone_answers(game, Random(0))
        winner_id, _ = game.proposals()[0]
        game.players[winner_id].score = 1
        result = game.pick_winner(1, 1)
        assert result.game_over
        assert not game.started

    def test_cards_in_use_include_hands_answers_and_discards(self) -> None:
        game = started_game(czar=1)
        game.discarded_white_cards.add("old")
        game.submit_answers(2, [1], Random(0))
        in_use = game.white_cards_in_use()
        assert "old" in in_use
        assert "2-0" in in_use  # played this round
        assert "3-0" in in_use  # still in a hand


class TestDeparture:
    def test_leaving_the_lobby(self) -> None:
        game = Game(guild_id=1, category_id=2, board_id=3)
        game.add_player(1, channel_id=10)
        departure = game.remove_player(1, Random(0))
        assert departure.player.user_id == 1
        assert not game.players

    def test_game_stops_below_minimum(self) -> None:
        game = started_game(players=3)
        departure = game.remove_player(2, Random(0))
        assert departure.game_stopped
        assert not game.started
        assert game.round is None

    def test_czar_leaving_cancels_the_round_and_returns_cards(self) -> None:
        game = started_game(players=4, czar=1)
        game.submit_answers(2, [1], Random(0))
        departure = game.remove_player(1, Random(0))
        assert departure.round_cancelled
        assert game.round is None
        assert len(game.players[2].hand) == HAND_SIZE
        assert game.players[2].hand[-1].id == "2-0", "the played card is back"
        assert game.next_czar_id == 2, "the role passes to the next player"

    def test_last_awaited_player_leaving_starts_judging(self) -> None:
        game = started_game(players=4, czar=1)
        game.submit_answers(2, [1], Random(0))
        game.submit_answers(3, [1], Random(0))
        departure = game.remove_player(4, Random(0))
        assert departure.judging_started
        assert game.phase is Phase.JUDGING

    def test_leaving_while_judging_withdraws_the_answer(self) -> None:
        game = started_game(players=4, czar=1)
        everyone_answers(game, Random(0))
        game.remove_player(3, Random(0))
        assert sorted(uid for uid, _ in game.proposals()) == [2, 4]

    def test_round_cancelled_when_no_participant_remains(self) -> None:
        game = started_game(players=3, czar=1)
        game.add_player(8, channel_id=108)
        game.add_player(9, channel_id=109)
        game.remove_player(2, Random(0))
        departure = game.remove_player(3, Random(0))
        assert departure.round_cancelled
        assert game.started


class TestOfficialRules:
    def test_czar_rotates_in_join_order(self) -> None:
        game = started_game(players=3, czar=1, points=10)
        czars = []
        for _ in range(4):
            assert game.round is not None
            czars.append(game.round.czar_id)
            everyone_answers(game, Random(0))
            game.pick_winner(game.round.czar_id, 1)
            for uid, count in game.cards_needed().items():
                game.deal(uid, hand(100 + uid)[:count])
            game.begin_round(BlackCard(id=f"q{len(czars)}", text="_?"), Random(0))
        assert czars == [1, 2, 3, 1]

    def test_rotation_skips_players_who_left(self) -> None:
        game = started_game(players=4, czar=1)
        game.remove_player(2, Random(0))
        everyone_answers(game, Random(0))
        game.pick_winner(1, 1)
        assert game.next_czar_id == 3

    def test_house_rule_winner_becomes_czar(self) -> None:
        game = Game(guild_id=1, category_id=2, board_id=3)
        for uid in (1, 2, 3):
            game.add_player(uid, channel_id=100 + uid)
            game.deal(uid, hand(uid))
        game.start(points=5, winner_becomes_czar=True)
        game.next_czar_id = 1
        game.begin_round(QUESTION, Random(0))
        everyone_answers(game, Random(0))
        winner_id, _ = game.proposals()[0]
        game.pick_winner(1, 1)
        assert game.next_czar_id == winner_id

    def test_draw_two_pick_three(self) -> None:
        card = BlackCard(id="q3", text="_, _ and _.", pick=3)
        assert card.draw == 2
        game = started_game(card=card, czar=1)
        assert game.cards_needed() == {2: 2, 3: 2}, "the Card Czar draws nothing extra"

    def test_pick_one_and_two_draw_nothing(self) -> None:
        assert QUESTION.draw == 0
        assert DOUBLE.draw == 0

    @pytest.mark.parametrize("pick", [0, 4, 10])
    def test_unplayable_black_cards_are_refused(self, pick: int) -> None:
        card = BlackCard(id="big", text="Pick many.", pick=pick)
        assert not card.playable
        game = Game(guild_id=1, category_id=2, board_id=3)
        for uid in (1, 2, 3):
            game.add_player(uid, channel_id=100 + uid)
        game.start(points=5)
        with pytest.raises(ValueError, match="asks for"):
            game.begin_round(card, Random(0))

    def test_three_players_minimum(self) -> None:
        game = Game(guild_id=1, category_id=2, board_id=3)
        game.add_player(1, channel_id=10)
        game.add_player(2, channel_id=20)
        with pytest.raises(NotEnoughPlayersError):
            game.start(points=5)
