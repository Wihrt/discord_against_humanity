"""Domain errors.

Every error carries a human-readable message that adapters can show
to the end user as-is.
"""


class DomainError(Exception):
    """Base class for all rule violations."""


class GameAlreadyExistsError(DomainError):
    def __init__(self) -> None:
        super().__init__("A game already exists in this server.")


class NoGameError(DomainError):
    def __init__(self) -> None:
        super().__init__("There is no game in this server. Use `/create` first.")


class AlreadyPlayerError(DomainError):
    def __init__(self) -> None:
        super().__init__("You are already in the game.")


class NotAPlayerError(DomainError):
    def __init__(self) -> None:
        super().__init__("You are not in the game. Use `/join` first.")


class GameAlreadyStartedError(DomainError):
    def __init__(self) -> None:
        super().__init__("The game has already started.")


class GameNotStartedError(DomainError):
    def __init__(self) -> None:
        super().__init__("The game has not started yet. Use `/start`.")


class NotEnoughPlayersError(DomainError):
    def __init__(self, minimum: int) -> None:
        super().__init__(f"At least {minimum} players are needed to start.")


class InvalidPointsError(DomainError):
    def __init__(self, minimum: int, maximum: int) -> None:
        super().__init__(f"Points to win must be between {minimum} and {maximum}.")


class InvalidTimerError(DomainError):
    def __init__(self, minimum: int, maximum: int) -> None:
        super().__init__(f"The timer must be 0 (off) or between {minimum} and {maximum} seconds.")


class WrongPhaseError(DomainError):
    """The action is not allowed at this moment of the round."""


class InvalidChoiceError(DomainError):
    """The submitted card numbers are not acceptable."""


class DeckExhaustedError(DomainError):
    def __init__(self) -> None:
        super().__init__("There are not enough cards left in the deck.")
