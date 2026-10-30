import pytest

from discord_against_humanity.domain.cards import BlackCard


@pytest.mark.parametrize(
    ("text", "answers", "expected"),
    [
        ("_ is great.", ["Cake"], "Cake is great."),
        ("_ and _.", ["A", "B"], "A and B."),
        ("Long ____ blank.", ["X"], "Long X blank."),
        ("What is love?", ["Cake"], "What is love? Cake"),
        ("Only _ here.", ["A", "B"], "Only A here. B"),
        ("_ and _.", ["A"], "A and _."),
    ],
)
def test_fill(text: str, answers: list[str], expected: str) -> None:
    assert BlackCard(id="b", text=text).fill(answers) == expected
