"""Game aggregate: players, rounds and the rules that tie them together.

This module is pure Python: it performs no I/O and knows nothing about
Discord or the storage backend.  Identifiers (guild, channel, user) are
plain integers handed over by the adapters.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from random import Random

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

HAND_SIZE = 7
MIN_PLAYERS = 2
MIN_POINTS = 1
MAX_POINTS = 50
DEFAULT_POINTS = 5


class Phase(StrEnum):
    LOBBY = "lobby"
    ANSWERING = "answering"
    JUDGING = "judging"


@dataclass(slots=True)
class Player:
    user_id: int
    channel_id: int
    score: int = 0
    hand: list[WhiteCard] = field(default_factory=list)


@dataclass(slots=True)
class Round:
    black_card: BlackCard
    tsar_id: int
    # Players expected to answer: everyone but the tsar, as of round start.
    participants: list[int]
    answers: dict[int, list[WhiteCard]] = field(default_factory=dict)
    # Shuffled answer owners, filled once every participant has answered.
    proposals: list[int] = field(default_factory=list)

    @property
    def judging(self) -> bool:
        return bool(self.proposals)


@dataclass(frozen=True, slots=True)
class RoundResult:
    winner_id: int
    black_card: BlackCard
    answers: tuple[WhiteCard, ...]
    game_over: bool


@dataclass(frozen=True, slots=True)
class Departure:
    player: Player
    round_cancelled: bool = False
    judging_started: bool = False
    game_stopped: bool = False


@dataclass(slots=True)
class Game:
    guild_id: int
    category_id: int
    board_id: int
    players: dict[int, Player] = field(default_factory=dict)
    points_to_win: int = DEFAULT_POINTS
    started: bool = False
    round: Round | None = None
    next_tsar_id: int | None = None
    used_black_cards: set[str] = field(default_factory=set)
    discarded_white_cards: set[str] = field(default_factory=set)

    # Queries
    # -------------------------------------------------------------------------

    @property
    def phase(self) -> Phase:
        if self.round is None:
            return Phase.LOBBY
        return Phase.JUDGING if self.round.judging else Phase.ANSWERING

    def has_player(self, user_id: int) -> bool:
        return user_id in self.players

    def player(self, user_id: int) -> Player:
        try:
            return self.players[user_id]
        except KeyError:
            raise NotAPlayerError from None

    def scoreboard(self) -> list[Player]:
        return sorted(self.players.values(), key=lambda p: p.score, reverse=True)

    def cards_needed(self) -> dict[int, int]:
        """Number of white cards each player must draw to fill their hand."""
        return {
            uid: HAND_SIZE - len(p.hand)
            for uid, p in self.players.items()
            if len(p.hand) < HAND_SIZE
        }

    def white_cards_in_use(self) -> set[str]:
        """IDs of white cards that must not be dealt again."""
        in_use = set(self.discarded_white_cards)
        for player in self.players.values():
            in_use.update(card.id for card in player.hand)
        if self.round is not None:
            for cards in self.round.answers.values():
                in_use.update(card.id for card in cards)
        return in_use

    def proposals(self) -> list[tuple[int, list[WhiteCard]]]:
        """Answers in reveal order, as ``(owner_id, cards)`` pairs."""
        round_ = self._round_in(Phase.JUDGING)
        return [(uid, round_.answers[uid]) for uid in round_.proposals]

    # Lobby
    # -------------------------------------------------------------------------

    def add_player(self, user_id: int, channel_id: int) -> Player:
        if user_id in self.players:
            raise AlreadyPlayerError
        player = Player(user_id=user_id, channel_id=channel_id)
        self.players[user_id] = player
        return player

    def remove_player(self, user_id: int, rng: Random) -> Departure:
        player = self.player(user_id)
        del self.players[user_id]
        if self.next_tsar_id == user_id:
            self.next_tsar_id = None

        if self.started and len(self.players) < MIN_PLAYERS:
            self.stop()
            return Departure(player, game_stopped=True)

        round_ = self.round
        if round_ is None:
            return Departure(player)

        round_.answers.pop(user_id, None)
        if user_id in round_.participants:
            round_.participants.remove(user_id)
        if user_id in round_.proposals:
            round_.proposals.remove(user_id)

        if user_id == round_.tsar_id or not round_.participants:
            self._cancel_round()
            return Departure(player, round_cancelled=True)
        return Departure(player, judging_started=self._maybe_start_judging(rng))

    def start(self, points: int) -> None:
        if self.started:
            raise GameAlreadyStartedError
        if not MIN_POINTS <= points <= MAX_POINTS:
            raise InvalidPointsError(MIN_POINTS, MAX_POINTS)
        if len(self.players) < MIN_PLAYERS:
            raise NotEnoughPlayersError(MIN_PLAYERS)
        self.started = True
        self.points_to_win = points
        for player in self.players.values():
            player.score = 0

    def stop(self) -> None:
        if not self.started:
            raise GameNotStartedError
        self._cancel_round()
        self.started = False

    # Rounds
    # -------------------------------------------------------------------------

    def deal(self, user_id: int, cards: Sequence[WhiteCard]) -> None:
        self.player(user_id).hand.extend(cards)

    def begin_round(self, black_card: BlackCard, rng: Random) -> Round:
        if not self.started:
            raise GameNotStartedError
        if self.round is not None:
            raise WrongPhaseError("A round is already in progress.")
        tsar_id = self.next_tsar_id
        if tsar_id not in self.players:
            tsar_id = rng.choice(list(self.players))
        self.next_tsar_id = tsar_id
        self.used_black_cards.add(black_card.id)
        self.round = Round(
            black_card=black_card,
            tsar_id=tsar_id,
            participants=[uid for uid in self.players if uid != tsar_id],
        )
        return self.round

    def submit_answers(self, user_id: int, choices: Sequence[int], rng: Random) -> bool:
        """Play cards from the player's hand.

        Args:
            user_id: The answering player.
            choices: 1-based positions of the cards in the player's hand.
            rng: Random source used to shuffle the proposals.

        Returns:
            True when this was the last awaited answer and judging begins.
        """
        player = self.player(user_id)
        round_ = self._round_in(Phase.ANSWERING)
        if user_id == round_.tsar_id:
            raise WrongPhaseError("The tsar does not answer, they judge!")
        if user_id not in round_.participants:
            raise WrongPhaseError("You joined during this round, wait for the next one.")
        if user_id in round_.answers:
            raise WrongPhaseError("You have already answered this round.")

        pick = round_.black_card.pick
        if len(choices) != pick:
            raise InvalidChoiceError(f"You must pick exactly {pick} card(s).")
        if len(set(choices)) != len(choices):
            raise InvalidChoiceError("You cannot pick the same card twice.")
        if not all(1 <= choice <= len(player.hand) for choice in choices):
            raise InvalidChoiceError(f"Card numbers must be between 1 and {len(player.hand)}.")

        round_.answers[user_id] = [player.hand[choice - 1] for choice in choices]
        for index in sorted(choices, reverse=True):
            del player.hand[index - 1]
        return self._maybe_start_judging(rng)

    def pick_winner(self, user_id: int, choice: int) -> RoundResult:
        self.player(user_id)
        round_ = self._round_in(Phase.JUDGING)
        if user_id != round_.tsar_id:
            raise WrongPhaseError("Only the tsar can pick the winner.")
        if not 1 <= choice <= len(round_.proposals):
            raise InvalidChoiceError(
                f"Answer number must be between 1 and {len(round_.proposals)}."
            )

        winner_id = round_.proposals[choice - 1]
        winner = self.players[winner_id]
        winner.score += 1
        for cards in round_.answers.values():
            self.discarded_white_cards.update(card.id for card in cards)
        # House rule kept from the original bot: the winner judges next.
        self.next_tsar_id = winner_id
        self.round = None

        game_over = winner.score >= self.points_to_win
        if game_over:
            self.started = False
        return RoundResult(
            winner_id=winner_id,
            black_card=round_.black_card,
            answers=tuple(round_.answers[winner_id]),
            game_over=game_over,
        )

    # Internals
    # -------------------------------------------------------------------------

    def _round_in(self, phase: Phase) -> Round:
        if not self.started:
            raise GameNotStartedError
        if self.round is None or self.phase is not phase:
            expected = {
                Phase.ANSWERING: "It is not time to answer.",
                Phase.JUDGING: "It is not time to judge.",
            }
            raise WrongPhaseError(expected.get(phase, "Wrong phase."))
        return self.round

    def _maybe_start_judging(self, rng: Random) -> bool:
        round_ = self.round
        if round_ is None or round_.judging:
            return False
        if not all(uid in round_.answers for uid in round_.participants):
            return False
        proposals = list(round_.participants)
        rng.shuffle(proposals)
        round_.proposals = proposals
        return True

    def _cancel_round(self) -> None:
        """Abort the current round, giving played cards back to their owners."""
        if self.round is None:
            return
        for uid, cards in self.round.answers.items():
            if uid in self.players:
                self.players[uid].hand.extend(cards)
        self.round = None
