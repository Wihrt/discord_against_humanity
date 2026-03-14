"""Discord Embed builder utility."""

from typing import Any

from discord import Embed


def create_embed(embed: dict[str, Any]) -> Embed:
    """Create a Discord Embed from a dictionary specification.

    Args:
        embed: Dictionary containing embed properties. Supports keys:
            title, description, color/colour, fields, author, footer,
            thumbnail, url.

    Returns:
        A configured Discord Embed.
    """
    message = Embed()
    for key, value in embed.items():
        if key == "author":
            message.set_author(**value)
        elif key == "fields":
            if isinstance(value, dict):
                message.add_field(**value)
            elif isinstance(value, list):
                for field in value:
                    message.add_field(**field)
        elif key == "footer":
            message.set_footer(**value)
        elif key == "thumbnail":
            message.set_thumbnail(url=value)
        elif key == "url":
            message.set_image(url=value)
        else:
            setattr(message, key, value)
    return message
