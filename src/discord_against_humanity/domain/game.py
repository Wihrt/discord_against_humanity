"""Game aggregate: players, rounds and the rules that tie them together.

This module is pure Python: it performs no I/O and knows nothing about
Discord or the storage backend.  Identifiers (guild, channel, user) are
plain integers handed over by the adapters.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from random import Random

from discord_against_humanity.domain.cards import BlackCard, WhiteCard
from discord_against_humanity.domain.errors import (
    AlreadyPlayerError,
    GameAlreadyStartedError,
    GameNotStartedError,
    InvalidChoiceError,
    InvalidPointsError,
    InvalidTimerError,
    NotAPlayerError,
    NotEnoughPlayersError,
    WrongPhaseError,
)

HAND_SIZE = 10
MIN_PLAYERS = 3
MIN_POINTS = 1
MAX_POINTS = 50
DEFAULT_POINTS = 5
# Seconds allowed to answer, then to judge. 0 disables the timer.
DEFAULT_TURN_SECONDS = 120
MIN_TURN_SECONDS = 15
MAX_TURN_SECONDS = 600


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
    czar_id: int
    # Players expected to answer: everyone but the czar, as of round start.
    participants: list[int]
    answers: dict[int, list[WhiteCard]] = field(default_factory=dict)
    # Shuffled answer owners, filled once every participant has answered.
    proposals: list[int] = field(default_factory=list)
    # When the current phase (answering, then judging) times out.
    deadline: datetime | None = None

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


@dataclass(frozen=True, slots=True)
class Timeout:
    """What happened when a phase ran out of time."""

    phase: Phase
    # Players who did not answer in time, or the Card Czar who did not judge.
    late: tuple[int, ...]
    judging_started: bool = False
    round_cancelled: bool = False


@dataclass(slots=True)
class Game:
    guild_id: int
    category_id: int
    board_id: int
    players: dict[int, Player] = field(default_factory=dict)
    points_to_win: int = DEFAULT_POINTS
    started: bool = False
    round: Round | None = None
    next_czar_id: int | None = None
    # House rule from the original bot: the round winner judges next.
    winner_becomes_czar: bool = False
    turn_seconds: int = DEFAULT_TURN_SECONDS
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
        """Number of white cards each player must draw before answering.

        Everyone fills their hand up to ``HAND_SIZE``; on "Draw 2, Pick 3"
        cards, the players who answer draw the extra cards on top.
        """
        extra = self.round.black_card.draw if self.round is not None else 0
        needed: dict[int, int] = {}
        for uid, player in self.players.items():
            bonus = extra if self.round is not None and uid in self.round.participants else 0
            count = max(HAND_SIZE - len(player.hand), 0) + bonus
            if count:
                needed[uid] = count
        return needed

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

    def remove_player(self, user_id: int, rng: Random, now: datetime | None = None) -> Departure:
        player = self.player(user_id)
        order = list(self.players)
        del self.players[user_id]
        if self.next_czar_id == user_id:
            self.next_czar_id = self._successor(user_id, order)

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

        if user_id == round_.czar_id or not round_.participants:
            self._cancel_round()
            return Departure(player, round_cancelled=True)
        return Departure(player, judging_started=self._maybe_start_judging(rng, now))

    def start(
        self,
        points: int,
        *,
        winner_becomes_czar: bool = False,
        turn_seconds: int = DEFAULT_TURN_SECONDS,
    ) -> None:
        if self.started:
            raise GameAlreadyStartedError
        if not MIN_POINTS <= points <= MAX_POINTS:
            raise InvalidPointsError(MIN_POINTS, MAX_POINTS)
        if turn_seconds and not MIN_TURN_SECONDS <= turn_seconds <= MAX_TURN_SECONDS:
            raise InvalidTimerError(MIN_TURN_SECONDS, MAX_TURN_SECONDS)
        if len(self.players) < MIN_PLAYERS:
            raise NotEnoughPlayersError(MIN_PLAYERS)
        self.started = True
        self.points_to_win = points
        self.winner_becomes_czar = winner_becomes_czar
        self.turn_seconds = turn_seconds
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

    def begin_round(self, black_card: BlackCard, rng: Random, now: datetime | None = None) -> Round:
        """Open a round. Without *now*, the round has no deadline."""
        if not self.started:
            raise GameNotStartedError
        if self.round is not None:
            raise WrongPhaseError("A round is already in progress.")
        if not black_card.playable:
            raise ValueError(f"Black card {black_card.id} asks for {black_card.pick} cards")
        czar_id = self.next_czar_id
        if czar_id not in self.players:
            czar_id = rng.choice(list(self.players))
        self.next_czar_id = czar_id
        self.used_black_cards.add(black_card.id)
        self.round = Round(
            black_card=black_card,
            czar_id=czar_id,
            participants=[uid for uid in self.players if uid != czar_id],
            deadline=self._deadline(now),
        )
        return self.round

    def submit_answers(
        self, user_id: int, choices: Sequence[int], rng: Random, now: datetime | None = None
    ) -> bool:
        """Play cards from the player's hand.

        Args:
            user_id: The answering player.
            choices: 1-based positions of the cards in the player's hand.
            rng: Random source used to shuffle the proposals.
            now: Current time, to set the judging deadline.

        Returns:
            True when this was the last awaited answer and judging begins.
        """
        player = self.player(user_id)
        round_ = self._round_in(Phase.ANSWERING)
        if user_id == round_.czar_id:
            raise WrongPhaseError("The Card Czar does not answer, they judge!")
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
        return self._maybe_start_judging(rng, now)

    def pick_winner(self, user_id: int, choice: int) -> RoundResult:
        self.player(user_id)
        round_ = self._round_in(Phase.JUDGING)
        if user_id != round_.czar_id:
            raise WrongPhaseError("Only the Card Czar can pick the winner.")
        if not 1 <= choice <= len(round_.proposals):
            raise InvalidChoiceError(
                f"Answer number must be between 1 and {len(round_.proposals)}."
            )

        winner_id = round_.proposals[choice - 1]
        winner = self.players[winner_id]
        winner.score += 1
        for cards in round_.answers.values():
            self.discarded_white_cards.update(card.id for card in cards)
        # Official rules: the Card Czar role passes to the next player.
        self.next_czar_id = (
            winner_id
            if self.winner_becomes_czar
            else self._successor(round_.czar_id, list(self.players))
        )
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

    def expire(self, now: datetime, rng: Random) -> Timeout | None:
        """Apply the timer if the current phase is past its deadline.

        - Answering: late players sit this round out and the Card Czar judges
          the answers received; with no answer at all, the round is skipped.
        - Judging: the round is skipped, played cards go back to their owners
          and the Card Czar role passes to the next player.
        """
        round_ = self.round
        if not self.started or round_ is None or round_.deadline is None:
            return None
        if now < round_.deadline:
            return None

        if round_.judging:
            self.next_czar_id = self._successor(round_.czar_id, list(self.players))
            self._cancel_round()
            return Timeout(Phase.JUDGING, (round_.czar_id,), round_cancelled=True)

        late = tuple(uid for uid in round_.participants if uid not in round_.answers)
        if not round_.answers:
            self.next_czar_id = self._successor(round_.czar_id, list(self.players))
            self._cancel_round()
            return Timeout(Phase.ANSWERING, late, round_cancelled=True)
        round_.participants = [uid for uid in round_.participants if uid in round_.answers]
        self._maybe_start_judging(rng, now)
        return Timeout(Phase.ANSWERING, late, judging_started=True)

    # Internals
    # -------------------------------------------------------------------------

    def _deadline(self, now: datetime | None) -> datetime | None:
        if now is None or not self.turn_seconds:
            return None
        return now + timedelta(seconds=self.turn_seconds)

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

    def _successor(self, user_id: int, order: Sequence[int]) -> int | None:
        """The player after *user_id* in join order, skipping those who left."""
        if user_id not in order:
            return None
        start = order.index(user_id)
        for offset in range(1, len(order)):
            candidate = order[(start + offset) % len(order)]
            if candidate in self.players:
                return candidate
        return None

    def _maybe_start_judging(self, rng: Random, now: datetime | None = None) -> bool:
        round_ = self.round
        if round_ is None or round_.judging:
            return False
        if not all(uid in round_.answers for uid in round_.participants):
            return False
        proposals = list(round_.participants)
        rng.shuffle(proposals)
        round_.proposals = proposals
        round_.deadline = self._deadline(now)
        return True

    def _cancel_round(self) -> None:
        """Abort the current round, giving played cards back to their owners."""
        if self.round is None:
            return
        for uid, cards in self.round.answers.items():
            if uid in self.players:
                self.players[uid].hand.extend(cards)
        self.round = None
