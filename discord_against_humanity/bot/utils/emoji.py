#!/bin/env python

from discord.utils import get

# Constants
NUMBERS = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]


def get_emojis(guild_emojis, number):
    emojis = list()

    if not isinstance(number, int):
        raise TypeError("Number should be an int")
    if not number in range(1, 10):
        raise ValueError("Number should be between 1 and 10")

    for n in NUMBERS[:number]:
        emojis.append(get(guild_emojis, name=n))
    return emojis

def find_emojis_used(guild_emojis, number, reactions):
    index_used = list()
    emojis = get_emojis(guild_emojis, number)
    for reaction in reactions:
        if reaction.count > 1:
            for index, emoji in enumerate(emojis):
                if reaction.emoji == emoji:
                    index_used.append(index + 1)
    return index_used
