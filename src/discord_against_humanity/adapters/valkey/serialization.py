"""JSON mapping of the game aggregate, kept out of the domain on purpose."""

from typing import Any

from discord_against_humanity.domain.cards import BlackCard, WhiteCard
from discord_against_humanity.domain.game import Game, Player, Round

SCHEMA_VERSION = 1


def _white(card: WhiteCard) -> dict[str, Any]:
    return {"id": card.id, "text": card.text}


def _white_from(data: dict[str, Any]) -> WhiteCard:
    return WhiteCard(id=data["id"], text=data["text"])


def _black(card: BlackCard) -> dict[str, Any]:
    return {"id": card.id, "text": card.text, "pick": card.pick}


def _black_from(data: dict[str, Any]) -> BlackCard:
    return BlackCard(id=data["id"], text=data["text"], pick=data["pick"])


def _round(round_: Round) -> dict[str, Any]:
    return {
        "black_card": _black(round_.black_card),
        "czar_id": round_.czar_id,
        "participants": list(round_.participants),
        # JSON object keys must be strings, so answers are stored as pairs.
        "answers": [
            [uid, [_white(card) for card in cards]] for uid, cards in round_.answers.items()
        ],
        "proposals": list(round_.proposals),
    }


def _round_from(data: dict[str, Any]) -> Round:
    return Round(
        black_card=_black_from(data["black_card"]),
        czar_id=data["czar_id"],
        participants=list(data["participants"]),
        answers={uid: [_white_from(c) for c in cards] for uid, cards in data["answers"]},
        proposals=list(data["proposals"]),
    )


def game_to_dict(game: Game) -> dict[str, Any]:
    return {
        "version": SCHEMA_VERSION,
        "guild_id": game.guild_id,
        "category_id": game.category_id,
        "board_id": game.board_id,
        "players": [
            {
                "user_id": p.user_id,
                "channel_id": p.channel_id,
                "score": p.score,
                "hand": [_white(card) for card in p.hand],
            }
            for p in game.players.values()
        ],
        "points_to_win": game.points_to_win,
        "started": game.started,
        "round": _round(game.round) if game.round is not None else None,
        "next_czar_id": game.next_czar_id,
        "winner_becomes_czar": game.winner_becomes_czar,
        "used_black_cards": sorted(game.used_black_cards),
        "discarded_white_cards": sorted(game.discarded_white_cards),
    }


def game_from_dict(data: dict[str, Any]) -> Game:
    if data.get("version") != SCHEMA_VERSION:
        raise ValueError(f"Unsupported game schema version: {data.get('version')}")
    players = {
        p["user_id"]: Player(
            user_id=p["user_id"],
            channel_id=p["channel_id"],
            score=p["score"],
            hand=[_white_from(c) for c in p["hand"]],
        )
        for p in data["players"]
    }
    return Game(
        guild_id=data["guild_id"],
        category_id=data["category_id"],
        board_id=data["board_id"],
        players=players,
        points_to_win=data["points_to_win"],
        started=data["started"],
        round=_round_from(data["round"]) if data["round"] is not None else None,
        next_czar_id=data["next_czar_id"],
        winner_becomes_czar=data.get("winner_becomes_czar", False),
        used_black_cards=set(data["used_black_cards"]),
        discarded_white_cards=set(data["discarded_white_cards"]),
    )
