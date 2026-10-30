"""Rendering of game state into Discord embeds and texts."""

from collections.abc import Sequence
from datetime import datetime

import discord

from discord_against_humanity.domain.cards import BlackCard, WhiteCard
from discord_against_humanity.domain.game import Game, Round, RoundResult

_BLACK = discord.Colour.dark_theme()
_WHITE = discord.Colour.light_grey()
_GOLD = discord.Colour.gold()


def mention(user_id: int) -> str:
    return f"<@{user_id}>"


def channel_mention(channel_id: int) -> str:
    return f"<#{channel_id}>"


def closes_in(deadline: datetime | None, label: str) -> str:
    """A live Discord countdown, e.g. " Answers close in 2 minutes."."""
    if deadline is None:
        return ""
    return f" {label} <t:{int(deadline.timestamp())}:R>."


def question_text(card: BlackCard) -> str:
    return card.text.replace("_", r"\_\_\_")


def answer_text(card: BlackCard, answers: Sequence[WhiteCard]) -> str:
    return card.fill([f"**{answer.text.rstrip('.')}**" for answer in answers])


def draft_text(card: BlackCard, answers: Sequence[WhiteCard]) -> str:
    """Like :func:`answer_text`, showing the blanks that are still empty."""
    missing = max(card.pick - len(answers), 0)
    return card.fill([f"**{a.text.rstrip('.')}**" for a in answers] + [r"\_\_\_"] * missing)


def rules_embed() -> discord.Embed:
    embed = discord.Embed(title="How to play", colour=_BLACK)
    embed.description = (
        "1. Each round, a **Card Czar** is chosen and a black card is drawn.\n"
        "2. Everyone else clicks white cards from their hand, in their private "
        "channel. The first card clicked fills the first blank.\n"
        "3. Once all answers are in, the Card Czar picks the funniest one.\n"
        "4. The winner scores a point, and the Card Czar role passes to the next player.\n"
        "5. The first player to reach the target score wins.\n\n"
        "`/hand` shows your cards, `/score` the scoreboard. "
        "`/vote` and `/czar` work too, e.g. `/vote answers:2 5`."
    )
    return embed


def question_embed(round_: Round) -> discord.Embed:
    card = round_.black_card
    return discord.Embed(
        title=f"Question — draw {card.draw}, pick {card.pick}"
        if card.draw
        else f"Question — pick {card.pick}",
        description=question_text(card),
        colour=_BLACK,
    ).set_footer(text="Card Czar: see the board")


def hand_embed(cards: Sequence[WhiteCard]) -> discord.Embed:
    lines = [f"`{index}.` {card.text}" for index, card in enumerate(cards, start=1)]
    return discord.Embed(
        title="Your hand",
        description="\n".join(lines) or "Your hand is empty.",
        colour=_WHITE,
    )


def play_embeds(
    round_: Round, hand: Sequence[WhiteCard], picked: Sequence[WhiteCard]
) -> list[discord.Embed]:
    """The question, the player's hand and their answer in progress."""
    embed = hand_embed(hand)
    embed.add_field(name="Your answer", value=draft_text(round_.black_card, picked), inline=False)
    return [question_embed(round_), embed]


def played_embed(card: BlackCard, played: Sequence[WhiteCard]) -> discord.Embed:
    return discord.Embed(
        title="Answer played", description=answer_text(card, played), colour=_WHITE
    ).set_footer(text="Waiting for the other players…")


def proposals_embed(game: Game, selected: int | None = None) -> discord.Embed:
    assert game.round is not None
    card = game.round.black_card
    lines = []
    for index, (_owner, cards) in enumerate(game.proposals(), start=1):
        marker = ":point_right: " if index == selected else ""
        lines.append(f"{marker}`{index}.` {answer_text(card, cards)}")
    return discord.Embed(title="Answers", description="\n".join(lines), colour=_WHITE)


def winner_embed(result: RoundResult) -> discord.Embed:
    return discord.Embed(
        title="Winning answer",
        description=answer_text(result.black_card, result.answers),
        colour=_GOLD,
    )


def scoreboard_embed(game: Game, title: str = "Scoreboard") -> discord.Embed:
    lines = [f"**{player.score}** — {mention(player.user_id)}" for player in game.scoreboard()]
    embed = discord.Embed(
        title=title,
        description="\n".join(lines) or "No players yet.",
        colour=_GOLD,
    )
    return embed.set_footer(text=f"First to {game.points_to_win} points wins")
