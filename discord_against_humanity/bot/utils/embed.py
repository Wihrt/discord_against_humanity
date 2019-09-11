#!/bin/env python

"""Utilities classes and functions"""

from discord import Embed

def create_embed(embed):
    """Create a complete Embed message

    Arguments:
        embed {dict} -- Contains all the elements of the Embed message

    Returns:
        Embed -- Embed message
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
