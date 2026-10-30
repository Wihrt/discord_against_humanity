import json
from pathlib import Path
from random import Random

import pytest

from discord_against_humanity.adapters.cah_json import load_source, parse_cards
from discord_against_humanity.adapters.memory import InMemoryCardStore
from discord_against_humanity.adapters.valkey.serialization import game_from_dict, game_to_dict
from discord_against_humanity.application.seeding import seed_cards
from discord_against_humanity.config import Settings
from discord_against_humanity.domain.cards import BlackCard, WhiteCard
from discord_against_humanity.domain.game import Game
from tests.unit.test_game import everyone_answers, started_game


class TestSerialization:
    def test_round_trip_lobby(self) -> None:
        game = Game(guild_id=1, category_id=2, board_id=3)
        game.add_player(7, channel_id=70)
        assert game_from_dict(json.loads(json.dumps(game_to_dict(game)))) == game

    def test_round_trip_mid_round(self) -> None:
        game = started_game(players=4, czar=2)
        game.discarded_white_cards.add("x")
        everyone_answers(game, Random(0))
        restored = game_from_dict(json.loads(json.dumps(game_to_dict(game))))
        assert restored == game
        assert restored.proposals() == game.proposals()

    def test_unknown_version_is_rejected(self) -> None:
        data = game_to_dict(Game(guild_id=1, category_id=2, board_id=3))
        data["version"] = 99
        with pytest.raises(ValueError, match="version"):
            game_from_dict(data)


class TestCahJson:
    COMPACT = {  # noqa: RUF012
        "white": ["Cake.", "Pie &amp; chips.", "Cake."],
        "black": [{"text": "_ is love.", "pick": 1}, {"text": "_ and _?", "pick": 2}],
        "packs": [
            {"name": "Base", "official": True, "white": [0], "black": [0]},
            {"name": "Fan", "official": False, "white": [1], "black": [1]},
        ],
    }

    def test_compact(self) -> None:
        black, white = parse_cards(self.COMPACT)
        assert [c.text for c in black] == ["_ is love.", "_ and _?"]
        assert [c.pick for c in black] == [1, 2]
        # Duplicates are merged and HTML entities decoded.
        assert [c.text for c in white] == ["Cake.", "Pie & chips."]

    def test_compact_official_only(self) -> None:
        black, white = parse_cards(self.COMPACT, official_only=True)
        assert [c.text for c in black] == ["_ is love."]
        assert [c.text for c in white] == ["Cake."]

    def test_full(self) -> None:
        data = [
            {"official": True, "white": [{"text": "A."}], "black": [{"text": "_?", "pick": 1}]},
            {"official": False, "white": [{"text": "B."}], "black": []},
        ]
        assert len(parse_cards(data)[1]) == 2
        assert len(parse_cards(data, official_only=True)[1]) == 1

    def test_legacy(self) -> None:
        black, white = parse_cards({"blackCards": [{"text": "_.", "pick": 1}], "whiteCards": ["A"]})
        assert len(black) == 1
        assert len(white) == 1

    def test_unplayable_black_cards_are_dropped(self) -> None:
        data = {
            "blackCards": [{"text": "_.", "pick": 1}, {"text": "List ten.", "pick": 10}],
            "whiteCards": ["A"],
        }
        assert [c.pick for c in parse_cards(data)[0]] == [1]

    def test_ids_are_stable(self) -> None:
        assert parse_cards(self.COMPACT) == parse_cards(self.COMPACT)

    def test_load_file(self, tmp_path: Path) -> None:
        path = tmp_path / "cards.json"
        path.write_text(json.dumps(self.COMPACT))
        assert load_source(str(path)) == self.COMPACT


class TestSeeding:
    async def test_seeds_an_empty_catalog(self) -> None:
        catalog = InMemoryCardStore()
        assert await seed_cards(catalog, [BlackCard("b", "_.")], [WhiteCard("w", "A")])
        assert await catalog.count() == (1, 1)

    async def test_skips_a_populated_catalog(self) -> None:
        catalog = InMemoryCardStore([BlackCard("b", "_.")], [WhiteCard("w", "A")])
        assert not await seed_cards(catalog, [BlackCard("c", "_?")], [])
        assert await catalog.count() == (1, 1)

    async def test_force_replaces(self) -> None:
        catalog = InMemoryCardStore([BlackCard("b", "_.")], [WhiteCard("w", "A")])
        assert await seed_cards(catalog, [BlackCard("c", "_?")], [], force=True)
        assert set(catalog.black) == {"c"}
        assert not catalog.white


def test_settings_from_env() -> None:
    settings = Settings.from_env(
        {"DISCORD_TOKEN": "t", "VALKEY_HOST": "kv", "VALKEY_PORT": "6380", "LOG_LEVEL": "debug"}
    )
    assert settings == Settings(
        discord_token="t", valkey_host="kv", valkey_port=6380, log_level="DEBUG"
    )
    assert Settings.from_env({}) == Settings()
