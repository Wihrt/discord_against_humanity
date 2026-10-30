from random import Random
from typing import Any, cast

import discord
import pytest
from discord import app_commands

from discord_against_humanity.adapters.discord import messages
from discord_against_humanity.adapters.discord.bot import error_message
from discord_against_humanity.adapters.discord.cog import parse_choices
from discord_against_humanity.adapters.discord.notifier import DiscordNotifier
from discord_against_humanity.domain.cards import BlackCard, WhiteCard
from discord_against_humanity.domain.errors import InvalidChoiceError, NoGameError
from tests.unit.test_game import everyone_answers, started_game


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("3", [3]), ("2 5", [2, 5]), (" 2, 5 ", [2, 5]), ("1;2;3", [1, 2, 3])],
)
def test_parse_choices(raw: str, expected: list[int]) -> None:
    assert parse_choices(raw) == expected


def test_parse_choices_rejects_garbage() -> None:
    with pytest.raises(InvalidChoiceError):
        parse_choices("two")


def test_domain_errors_are_shown_to_the_user() -> None:
    wrapped = app_commands.CommandInvokeError.__new__(app_commands.CommandInvokeError)
    wrapped.original = NoGameError()
    assert str(NoGameError()) in error_message(wrapped)


def test_unexpected_errors_stay_generic() -> None:
    wrapped = app_commands.CommandInvokeError.__new__(app_commands.CommandInvokeError)
    wrapped.original = RuntimeError("secret internals")
    assert "secret" not in error_message(wrapped)


def test_answer_text_highlights_answers() -> None:
    card = BlackCard(id="b", text="_ beats _.", pick=2)
    answers = [WhiteCard("1", "Rock."), WhiteCard("2", "Scissors")]
    assert messages.answer_text(card, answers) == "**Rock** beats **Scissors**."


def test_question_text_escapes_blanks() -> None:
    assert messages.question_text(BlackCard(id="b", text="_ is it.")) == r"\_\_\_ is it."


def test_proposals_embed_lists_every_answer() -> None:
    game = started_game(players=4)
    everyone_answers(game, Random(0))
    description = messages.proposals_embed(game).description or ""
    assert description.count("\n") == 2
    assert description.startswith("`1.`")


class FakeChannel(discord.abc.Messageable):
    def __init__(self) -> None:
        self.sent: list[tuple[str | None, dict[str, Any]]] = []

    async def _get_channel(self) -> Any:
        return self

    async def send(self, content: str | None = None, **kwargs: Any) -> Any:
        self.sent.append((content, kwargs))


class FakeClient:
    def __init__(self) -> None:
        self.channels: dict[int, FakeChannel] = {}

    def get_channel(self, channel_id: int) -> FakeChannel:
        return self.channels.setdefault(channel_id, FakeChannel())


async def test_round_started_reaches_every_player() -> None:
    client = FakeClient()
    notifier = DiscordNotifier(cast(discord.Client, client))
    game = started_game(players=3, czar=1)
    game.add_player(9, channel_id=109)

    await notifier.round_started(game)

    board = client.channels[game.board_id].sent
    assert "<@1>" in (board[0][0] or "")
    assert "Card Czar" in (client.channels[101].sent[0][0] or "")
    assert "first blank" in (client.channels[102].sent[0][0] or "")
    assert client.channels[102].sent[0][1]["view"] is not None
    assert len(client.channels[102].sent[0][1]["embeds"]) == 2
    assert "next one" in (client.channels[109].sent[0][0] or "")
