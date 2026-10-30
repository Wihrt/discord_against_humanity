"""Buttons to play cards and judge answers by clicking.

Click order is answer order: the first card clicked fills the first blank,
which reactions could not provide (Discord does not expose when a user
reacted). Each click is its own interaction, so the order is never lost.

All the state lives in the buttons' custom IDs (current round, cards picked
so far): the buttons keep working after a restart and the selection in
progress needs no storage. Only the final choice reaches the application
layer, through the same use cases as ``/vote`` and ``/tsar``.
"""

import logging
import re
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

import discord
from discord import ui

from discord_against_humanity.adapters.discord import messages
from discord_against_humanity.application.service import GameService
from discord_against_humanity.domain.cards import WhiteCard
from discord_against_humanity.domain.errors import DomainError, NoGameError, WrongPhaseError
from discord_against_humanity.domain.game import Game, Phase, Player, Round

logger = logging.getLogger(__name__)

# Discord allows 5 rows of 5 buttons; the last row holds the controls.
_MAX_CHOICES = 20
_ROW_WIDTH = 5
_ROUND = r"(?P<round>[\w-]+)"
_DRAFT = r"(?P<draft>[\d.]*)"


def encode_draft(draft: Sequence[int]) -> str:
    return ".".join(map(str, draft))


def decode_draft(raw: str) -> list[int]:
    return [int(part) for part in raw.split(".") if part]


def _service(interaction: discord.Interaction) -> GameService:
    service = getattr(interaction.client, "service", None)
    if not isinstance(service, GameService):
        raise RuntimeError("The client does not expose a GameService")
    return service


async def _load(interaction: discord.Interaction, round_id: str) -> tuple[Game, Player, Round]:
    """Load the game and check that the button belongs to this user and round."""
    if interaction.guild is None:
        raise NoGameError
    game = await _service(interaction).get(interaction.guild.id)
    player = game.player(interaction.user.id)
    if player.channel_id != interaction.channel_id:
        raise WrongPhaseError("These buttons are not yours.")
    if game.round is None or game.round.black_card.id != round_id:
        raise WrongPhaseError("This round is over.")
    return game, player, game.round


async def _guarded(interaction: discord.Interaction, action: Callable[[], Awaitable[None]]) -> None:
    """Run a button action, reporting rule violations to the clicker only."""
    try:
        await action()
    except DomainError as error:
        content = f":no_entry_sign: {error}"
    except Exception:
        logger.exception("Button %s failed", interaction.data)
        content = ":x: Something went wrong, please try again."
    else:
        return
    if interaction.response.is_done():
        await interaction.followup.send(content, ephemeral=True)
    else:
        await interaction.response.send_message(content, ephemeral=True)


# Answering
# -----------------------------------------------------------------------------


def hand_view(round_: Round, hand: Sequence[WhiteCard], draft: Sequence[int]) -> ui.View:
    """Card buttons; the ones already picked show which blank they fill."""
    view = ui.View(timeout=None)
    complete = len(draft) >= round_.black_card.pick
    for index in range(1, min(len(hand), _MAX_CHOICES) + 1):
        view.add_item(PlayCard(round_.black_card.id, draft, index, complete=complete))
    view.add_item(ResetDraft(round_.black_card.id, disabled=not draft))
    view.add_item(SubmitDraft(round_.black_card.id, draft, disabled=not complete))
    return view


def _picked(hand: Sequence[WhiteCard], draft: Sequence[int]) -> list[WhiteCard]:
    return [hand[index - 1] for index in draft if 1 <= index <= len(hand)]


class PlayCard(
    ui.DynamicItem[ui.Button[Any]],
    template=rf"cah:card:{_ROUND}:{_DRAFT}:(?P<index>\d+)",
):
    def __init__(
        self, round_id: str, draft: Sequence[int], index: int, *, complete: bool = False
    ) -> None:
        self.round_id = round_id
        self.draft = list(draft)
        self.index = index
        position = self.draft.index(index) + 1 if index in self.draft else None
        super().__init__(
            ui.Button(
                label=f"{index} → blank {position}" if position else str(index),
                style=discord.ButtonStyle.success if position else discord.ButtonStyle.secondary,
                disabled=position is not None or complete,
                custom_id=f"cah:card:{round_id}:{encode_draft(self.draft)}:{index}",
                row=(index - 1) // _ROW_WIDTH,
            )
        )

    @classmethod
    async def from_custom_id(
        cls, interaction: discord.Interaction, item: ui.Item[Any], match: re.Match[str], /
    ) -> PlayCard:
        return cls(match["round"], decode_draft(match["draft"]), int(match["index"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        async def action() -> None:
            _, player, round_ = await _load(interaction, self.round_id)
            draft = self.draft
            if (
                self.index not in draft
                and len(draft) < round_.black_card.pick
                and self.index <= len(player.hand)
            ):
                draft = [*draft, self.index]
            await interaction.response.edit_message(
                embeds=messages.play_embeds(round_, player.hand, _picked(player.hand, draft)),
                view=hand_view(round_, player.hand, draft),
            )

        await _guarded(interaction, action)


class ResetDraft(ui.DynamicItem[ui.Button[Any]], template=rf"cah:reset:{_ROUND}"):
    def __init__(self, round_id: str, *, disabled: bool = False) -> None:
        self.round_id = round_id
        super().__init__(
            ui.Button(
                label="Start over",
                style=discord.ButtonStyle.secondary,
                disabled=disabled,
                custom_id=f"cah:reset:{round_id}",
                row=4,
            )
        )

    @classmethod
    async def from_custom_id(
        cls, interaction: discord.Interaction, item: ui.Item[Any], match: re.Match[str], /
    ) -> ResetDraft:
        return cls(match["round"])

    async def callback(self, interaction: discord.Interaction) -> None:
        async def action() -> None:
            _, player, round_ = await _load(interaction, self.round_id)
            await interaction.response.edit_message(
                embeds=messages.play_embeds(round_, player.hand, []),
                view=hand_view(round_, player.hand, []),
            )

        await _guarded(interaction, action)


class SubmitDraft(ui.DynamicItem[ui.Button[Any]], template=rf"cah:submit:{_ROUND}:{_DRAFT}"):
    def __init__(self, round_id: str, draft: Sequence[int], *, disabled: bool = False) -> None:
        self.round_id = round_id
        self.draft = list(draft)
        super().__init__(
            ui.Button(
                label="Play",
                style=discord.ButtonStyle.primary,
                disabled=disabled,
                custom_id=f"cah:submit:{round_id}:{encode_draft(self.draft)}",
                row=4,
            )
        )

    @classmethod
    async def from_custom_id(
        cls, interaction: discord.Interaction, item: ui.Item[Any], match: re.Match[str], /
    ) -> SubmitDraft:
        return cls(match["round"], decode_draft(match["draft"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        async def action() -> None:
            game, player, round_ = await _load(interaction, self.round_id)
            played = _picked(player.hand, self.draft)
            # Acknowledge first: submitting notifies the board, which may be slow.
            await interaction.response.defer()
            await _service(interaction).submit_answers(
                game.guild_id, interaction.user.id, self.draft
            )
            await interaction.edit_original_response(
                embed=messages.played_embed(round_.black_card, played), view=None
            )

        await _guarded(interaction, action)


# Judging
# -----------------------------------------------------------------------------


def judge_view(round_: Round, selected: int | None = None) -> ui.View:
    view = ui.View(timeout=None)
    for choice in range(1, min(len(round_.proposals), _MAX_CHOICES) + 1):
        view.add_item(JudgeAnswer(round_.black_card.id, choice, selected=choice == selected))
    view.add_item(CrownAnswer(round_.black_card.id, selected))
    return view


async def _load_judging(interaction: discord.Interaction, round_id: str) -> tuple[Game, Round]:
    game, player, round_ = await _load(interaction, round_id)
    if player.user_id != round_.tsar_id:
        raise WrongPhaseError("Only the tsar can pick the winner.")
    if game.phase is not Phase.JUDGING:
        raise WrongPhaseError("It is not time to judge.")
    return game, round_


class JudgeAnswer(
    ui.DynamicItem[ui.Button[Any]],
    template=rf"cah:judge:{_ROUND}:(?P<choice>\d+)",
):
    def __init__(self, round_id: str, choice: int, *, selected: bool = False) -> None:
        self.round_id = round_id
        self.choice = choice
        super().__init__(
            ui.Button(
                label=str(choice),
                style=discord.ButtonStyle.success if selected else discord.ButtonStyle.secondary,
                custom_id=f"cah:judge:{round_id}:{choice}",
                row=(choice - 1) // _ROW_WIDTH,
            )
        )

    @classmethod
    async def from_custom_id(
        cls, interaction: discord.Interaction, item: ui.Item[Any], match: re.Match[str], /
    ) -> JudgeAnswer:
        return cls(match["round"], int(match["choice"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        async def action() -> None:
            game, round_ = await _load_judging(interaction, self.round_id)
            await interaction.response.edit_message(
                embed=messages.proposals_embed(game, selected=self.choice),
                view=judge_view(round_, self.choice),
            )

        await _guarded(interaction, action)


class CrownAnswer(ui.DynamicItem[ui.Button[Any]], template=rf"cah:crown:{_ROUND}:(?P<choice>\d*)"):
    def __init__(self, round_id: str, choice: int | None) -> None:
        self.round_id = round_id
        self.choice = choice
        super().__init__(
            ui.Button(
                label="Crown this answer",
                style=discord.ButtonStyle.primary,
                disabled=choice is None,
                custom_id=f"cah:crown:{round_id}:{choice or ''}",
                row=4,
            )
        )

    @classmethod
    async def from_custom_id(
        cls, interaction: discord.Interaction, item: ui.Item[Any], match: re.Match[str], /
    ) -> CrownAnswer:
        return cls(match["round"], int(match["choice"]) if match["choice"] else None)

    async def callback(self, interaction: discord.Interaction) -> None:
        async def action() -> None:
            if self.choice is None:
                raise WrongPhaseError("Pick an answer first.")
            game, _ = await _load_judging(interaction, self.round_id)
            embed = messages.proposals_embed(game, selected=self.choice)
            await interaction.response.defer()
            await _service(interaction).pick_winner(game.guild_id, interaction.user.id, self.choice)
            await interaction.edit_original_response(embed=embed, view=None)

        await _guarded(interaction, action)


DYNAMIC_ITEMS = (PlayCard, ResetDraft, SubmitDraft, JudgeAnswer, CrownAnswer)
