"""Tests for the emoji utility module."""

import pytest

from discord_against_humanity.utils.emoji import (
    NUMBER_EMOJIS,
    emoji_to_index,
    get_number_emojis,
)


class TestGetNumberEmojis:
    """Tests for get_number_emojis()."""

    def test_returns_one_emoji(self):
        result = get_number_emojis(1)
        assert result == ["1️⃣"]

    def test_returns_seven_emojis(self):
        result = get_number_emojis(7)
        assert len(result) == 7
        assert result[0] == "1️⃣"
        assert result[6] == "7️⃣"

    def test_returns_nine_emojis(self):
        result = get_number_emojis(9)
        assert len(result) == 9
        assert result == NUMBER_EMOJIS

    def test_rejects_zero(self):
        with pytest.raises(ValueError, match="count must be between 1 and 9"):
            get_number_emojis(0)

    def test_rejects_ten(self):
        with pytest.raises(ValueError, match="count must be between 1 and 9"):
            get_number_emojis(10)

    def test_rejects_negative(self):
        with pytest.raises(ValueError, match="count must be between 1 and 9"):
            get_number_emojis(-1)

    def test_rejects_string(self):
        with pytest.raises(TypeError, match="count must be an int"):
            get_number_emojis("3")  # type: ignore[arg-type]

    def test_rejects_float(self):
        with pytest.raises(TypeError, match="count must be an int"):
            get_number_emojis(3.0)  # type: ignore[arg-type]

    def test_returns_new_list(self):
        """Ensure the returned list is a copy, not the internal list."""
        a = get_number_emojis(3)
        b = get_number_emojis(3)
        assert a == b
        assert a is not b


class TestEmojiToIndex:
    """Tests for emoji_to_index()."""

    def test_first_emoji(self):
        assert emoji_to_index("1️⃣") == 0

    def test_last_emoji(self):
        assert emoji_to_index("9️⃣") == 8

    def test_middle_emoji(self):
        assert emoji_to_index("5️⃣") == 4

    def test_invalid_emoji_returns_none(self):
        assert emoji_to_index("👍") is None

    def test_empty_string_returns_none(self):
        assert emoji_to_index("") is None

    def test_text_returns_none(self):
        assert emoji_to_index("hello") is None

    def test_all_emojis_roundtrip(self):
        """Every emoji in NUMBER_EMOJIS maps to its correct index."""
        for i, emoji in enumerate(NUMBER_EMOJIS):
            assert emoji_to_index(emoji) == i
