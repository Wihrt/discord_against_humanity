"""Reader for the JSON card exports published by JSON Against Humanity.

See https://github.com/crhallberg/json-against-humanity.  Three layouts
are understood:

* compact: ``{"white": [str], "black": [{"text", "pick"}], "packs": [...]}``
* full: ``[{"name", "official", "white": [{"text"}], "black": [{"text", "pick"}]}]``
* legacy: ``{"whiteCards": [str], "blackCards": [{"text", "pick"}]}``
"""

import html
import json
import urllib.request
from hashlib import sha1
from pathlib import Path
from typing import Any

from discord_against_humanity.domain.cards import BlackCard, WhiteCard

DEFAULT_SOURCE = (
    "https://raw.githubusercontent.com/crhallberg/json-against-humanity/latest/cah-all-compact.json"
)
_TIMEOUT_SECONDS = 60


def load_source(source: str) -> Any:
    """Read JSON from a local path or an ``http(s)://`` URL."""
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source, timeout=_TIMEOUT_SECONDS) as response:  # noqa: S310
            return json.load(response)
    return json.loads(Path(source).read_text(encoding="utf-8"))


def _card_id(text: str) -> str:
    # Content-addressed IDs make seeding idempotent and drop duplicates
    # shared by several packs.
    return sha1(text.encode(), usedforsecurity=False).hexdigest()[:16]


def _clean(text: str) -> str:
    return html.unescape(text).strip()


def _white(text: str) -> WhiteCard:
    text = _clean(text)
    return WhiteCard(id=_card_id(text), text=text)


def _black(data: dict[str, Any]) -> BlackCard:
    text = _clean(data["text"])
    return BlackCard(id=_card_id(text), text=text, pick=int(data.get("pick", 1)))


def parse_cards(
    data: Any, *, official_only: bool = False
) -> tuple[list[BlackCard], list[WhiteCard]]:
    """Extract unique black and white cards from any supported layout."""
    raw_black: list[dict[str, Any]] = []
    raw_white: list[str] = []

    if isinstance(data, list):
        for pack in data:
            if official_only and not pack.get("official", False):
                continue
            raw_black.extend(pack.get("black", []))
            raw_white.extend(card["text"] for card in pack.get("white", []))
    elif "blackCards" in data:
        raw_black, raw_white = data["blackCards"], data["whiteCards"]
    elif official_only:
        black_ids: set[int] = set()
        white_ids: set[int] = set()
        for pack in data["packs"]:
            if pack.get("official", False):
                black_ids.update(pack["black"])
                white_ids.update(pack["white"])
        raw_black = [data["black"][i] for i in sorted(black_ids)]
        raw_white = [data["white"][i] for i in sorted(white_ids)]
    else:
        raw_black, raw_white = data["black"], data["white"]

    black = {card.id: card for card in map(_black, raw_black) if card.text}
    white = {card.id: card for card in map(_white, raw_white) if card.text}
    return list(black.values()), list(white.values())
