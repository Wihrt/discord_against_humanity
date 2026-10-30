"""Button flows, replayed through custom IDs exactly as Discord dispatches them."""

from types import SimpleNamespace
from typing import Any, cast

import discord
import pytest
from discord import ui

from discord_against_humanity.adapters.discord import views
from discord_against_humanity.adapters.memory import InMemoryCardStore, InMemoryGameRepository
from discord_against_humanity.application.service import GameService
from discord_against_humanity.domain.game import Game, Phase
from tests.conftest import (
    BOARD,
    CATEGORY,
    GUILD,
    RecordingNotifier,
    make_black_cards,
    make_white_cards,
)


class FakeResponse:
    def __init__(self) -> None:
        self.edits: list[dict[str, Any]] = []
        self.messages: list[str | None] = []
        self._done = False

    def is_done(self) -> bool:
        return self._done

    async def edit_message(self, **kwargs: Any) -> None:
        self.edits.append(kwargs)
        self._done = True

    async def defer(self, **_: Any) -> None:
        self._done = True

    async def send_message(self, content: str | None = None, **_: Any) -> None:
        self.messages.append(content)
        self._done = True


class FakeInteraction:
    def __init__(self, service: GameService, user_id: int, channel_id: int) -> None:
        self.guild = SimpleNamespace(id=GUILD)
        self.user = SimpleNamespace(id=user_id)
        self.channel_id = channel_id
        self.client = SimpleNamespace(service=service)
        self.response = FakeResponse()
        self.followup = SimpleNamespace(send=self._followup)
        self.data: dict[str, Any] = {}
        self.followups: list[str | None] = []
        self.original_edits: list[dict[str, Any]] = []

    async def _followup(self, content: str | None = None, **_: Any) -> None:
        self.followups.append(content)

    async def edit_original_response(self, **kwargs: Any) -> None:
        self.original_edits.append(kwargs)

    def errors(self) -> list[str | None]:
        return self.response.messages + self.followups


async def click(service: GameService, user_id: int, custom_id: str) -> FakeInteraction:
    """Dispatch a click the way discord.py does: match the template, rebuild, call back."""
    interaction = FakeInteraction(service, user_id, channel_id=100 + user_id)
    for cls in views.DYNAMIC_ITEMS:
        match = cls.__discord_ui_compiled_template__.fullmatch(custom_id)
        if match:
            item = await cls.from_custom_id(
                cast(discord.Interaction, interaction), cast(Any, None), match
            )
            await item.callback(cast(discord.Interaction, interaction))
            return interaction
    raise AssertionError(f"No dynamic item matches {custom_id!r}")


def button(view: ui.View, label: str) -> str:
    for item in view.children:
        assert isinstance(item, ui.DynamicItem)
        if getattr(item.item, "label", None) == label:
            return item.custom_id
    raise AssertionError(f"No button labelled {label!r}")


def disabled(view: ui.View, label: str) -> bool:
    for item in view.children:
        assert isinstance(item, ui.DynamicItem)
        if getattr(item.item, "label", None) == label:
            return bool(getattr(item.item, "disabled", False))
    raise AssertionError(f"No button labelled {label!r}")


@pytest.fixture
def service() -> GameService:
    deck = InMemoryCardStore(make_black_cards(pick=2), make_white_cards())
    return GameService(InMemoryGameRepository(), deck, RecordingNotifier())


async def started(service: GameService) -> Game:
    await service.create(GUILD, CATEGORY, BOARD)
    for uid in (1, 2, 3):
        await service.join(GUILD, uid, channel_id=100 + uid)
    return await service.start(GUILD, points=5)


async def test_click_order_is_answer_order(service: GameService) -> None:
    game = await started(service)
    assert game.round is not None
    uid = game.round.participants[0]
    hand = game.players[uid].hand
    view = views.hand_view(game.round, hand, [])
    assert disabled(view, "Play")

    first = await click(service, uid, button(view, "5"))
    view = first.response.edits[-1]["view"]
    assert disabled(view, "5 → blank 1")
    assert disabled(view, "Play"), "pick 2: one more card is needed"

    second = await click(service, uid, button(view, "2"))
    view = second.response.edits[-1]["view"]
    assert disabled(view, "2 → blank 2")
    assert disabled(view, "1"), "the answer is complete, other cards are locked"
    assert not disabled(view, "Play")

    played = await click(service, uid, button(view, "Play"))
    assert played.errors() == []
    assert played.original_edits[-1]["view"] is None

    game = await service.get(GUILD)
    assert game.round is not None
    assert game.round.answers[uid] == [hand[4], hand[1]]


async def test_start_over_clears_the_selection(service: GameService) -> None:
    game = await started(service)
    assert game.round is not None
    uid = game.round.participants[0]
    view = views.hand_view(game.round, game.players[uid].hand, [])
    view = (await click(service, uid, button(view, "3"))).response.edits[-1]["view"]
    view = (await click(service, uid, button(view, "Start over"))).response.edits[-1]["view"]
    assert not disabled(view, "3")
    assert disabled(view, "Start over")


async def test_someone_else_cannot_use_your_buttons(service: GameService) -> None:
    game = await started(service)
    assert game.round is not None
    owner, other = game.round.participants
    view = views.hand_view(game.round, game.players[owner].hand, [])
    interaction = FakeInteraction(service, other, channel_id=100 + owner)
    match = views.PlayCard.__discord_ui_compiled_template__.fullmatch(button(view, "1"))
    assert match is not None
    item = await views.PlayCard.from_custom_id(
        cast(discord.Interaction, interaction), cast(Any, None), match
    )
    await item.callback(cast(discord.Interaction, interaction))
    assert interaction.response.edits == []
    assert "not yours" in (interaction.errors()[0] or "")


async def test_buttons_from_a_previous_round_are_refused(service: GameService) -> None:
    game = await started(service)
    assert game.round is not None
    uid = game.round.participants[0]
    stale = button(views.hand_view(game.round, game.players[uid].hand, []), "1")
    await service.stop(GUILD)
    interaction = await click(service, uid, stale)
    assert "round is over" in (interaction.errors()[0] or "")


async def test_tsar_selects_then_crowns(service: GameService) -> None:
    game = await started(service)
    assert game.round is not None
    for uid in game.round.participants:
        await service.submit_answers(GUILD, uid, [1, 2])
    game = await service.get(GUILD)
    assert game.round is not None
    assert game.phase is Phase.JUDGING
    tsar = game.round.tsar_id
    expected_winner = game.round.proposals[1]

    view = views.judge_view(game.round)
    assert disabled(view, "Crown this answer")

    # A player cannot judge.
    refused = await click(service, game.round.participants[0], button(view, "2"))
    assert "Only the tsar" in (refused.errors()[0] or "")

    view = (await click(service, tsar, button(view, "2"))).response.edits[-1]["view"]
    crowned = await click(service, tsar, button(view, "Crown this answer"))
    assert crowned.errors() == []

    game = await service.get(GUILD)
    assert game.players[expected_winner].score == 1


@pytest.mark.parametrize(("raw", "draft"), [("", []), ("5", [5]), ("5.2.7", [5, 2, 7])])
def test_draft_encoding(raw: str, draft: list[int]) -> None:
    assert views.decode_draft(raw) == draft
    assert views.encode_draft(draft) == raw
