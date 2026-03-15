"""Emoji utilities for reaction-based voting."""

NUMBER_EMOJIS: list[str] = [
    "1️⃣",
    "2️⃣",
    "3️⃣",
    "4️⃣",
    "5️⃣",
    "6️⃣",
    "7️⃣",
    "8️⃣",
    "9️⃣",
]


def get_number_emojis(count: int) -> list[str]:
    """Return the first ``count`` Unicode number emojis.

    Args:
        count: How many emojis to return (1–9).

    Returns:
        A list of Unicode number emoji strings.

    Raises:
        TypeError: If *count* is not an int.
        ValueError: If *count* is not between 1 and 9.
    """
    if not isinstance(count, int):
        raise TypeError("count must be an int")
    if count < 1 or count > 9:
        raise ValueError("count must be between 1 and 9")
    return NUMBER_EMOJIS[:count]


def emoji_to_index(emoji: str) -> int | None:
    """Convert a Unicode number emoji to its 0-based index.

    ``"1️⃣"`` → ``0``, ``"2️⃣"`` → ``1``, etc.

    Args:
        emoji: The emoji string.

    Returns:
        The 0-based index, or ``None`` if *emoji* is not a number emoji.
    """
    try:
        return NUMBER_EMOJIS.index(str(emoji))
    except ValueError:
        return None
