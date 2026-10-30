"""Rendering of game state into Discord embeds and texts."""

from collections.abc import Sequence

import discord

from discord_against_humanity.domain.cards import BlackCard, WhiteCard
from discord_against_humanity.domain.game import Game, RoundResult

_BLACK = discord.Colour.dark_theme()
_WHITE = discord.Colour.light_grey()
_GOLD = discord.Colour.gold()


def mention(user_id: int) -> str:
    return f"<@{user_id}>"


def channel_mention(channel_id: int) -> str:
    return f"<#{channel_id}>"


def question_text(card: BlackCard) -> str:
    return card.text.replace("_", r"\_\_\_")


def answer_text(card: BlackCard, answers: Sequence[WhiteCard]) -> str:
    return card.fill([f"**{answer.text.rstrip('.')}**" for answer in answers])


def rules_embed() -> discord.Embed:
    embed = discord.Embed(title="How to play", colour=_BLACK)
    embed.description = (
        "1. Each round, a **tsar** is chosen and a black card is drawn.\n"
        "2. Everyone else picks white cards from their hand with `/vote` "
        "in their private channel, e.g. `/vote answers:3` or `/vote answers:2 5`.\n"
        "3. Once all answers are in, the tsar picks the funniest one with `/tsar`.\n"
        "4. The winner scores a point and becomes the next tsar.\n"
        "5. The first player to reach the target score wins.\n\n"
        "`/hand` shows your cards, `/score` the scoreboard."
    )
    return embed


def question_embed(game: Game) -> discord.Embed:
    assert game.round is not None
    card = game.round.black_card
    return discord.Embed(
        title=f"Question — pick {card.pick}",
        description=question_text(card),
        colour=_BLACK,
    ).set_footer(text="Tsar: see the board")


def hand_embed(cards: Sequence[WhiteCard]) -> discord.Embed:
    lines = [f"`{index}.` {card.text}" for index, card in enumerate(cards, start=1)]
    return discord.Embed(
        title="Your hand",
        description="\n".join(lines) or "Your hand is empty.",
        colour=_WHITE,
    )


def proposals_embed(game: Game) -> discord.Embed:
    assert game.round is not None
    card = game.round.black_card
    lines = [
        f"`{index}.` {answer_text(card, cards)}"
        for index, (_owner, cards) in enumerate(game.proposals(), start=1)
    ]
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
