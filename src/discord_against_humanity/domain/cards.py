"""Card value objects."""

import re
from collections.abc import Sequence
from dataclasses import dataclass

_BLANK = re.compile(r"_+")


@dataclass(frozen=True, slots=True)
class WhiteCard:
    """An answer card."""

    id: str
    text: str


@dataclass(frozen=True, slots=True)
class BlackCard:
    """A question card, with one or more blanks to fill."""

    id: str
    text: str
    pick: int = 1

    def fill(self, answers: Sequence[str]) -> str:
        """Return the card text with each blank replaced by an answer.

        Answers that have no matching blank (question-style cards) are
        appended at the end of the text.
        """
        remaining = list(answers)

        def substitute(_match: re.Match[str]) -> str:
            return remaining.pop(0) if remaining else _match.group(0)

        filled = _BLANK.sub(substitute, self.text)
        return " ".join([filled, *remaining])
