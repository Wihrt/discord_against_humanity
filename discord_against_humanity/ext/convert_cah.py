#!/usr/bin/env python

from json import dump, load
from os.path import join


def create_black_cards(directory, data):
    with open(join(directory, "black_cards.json"), "w") as fichier:
        dump(data, fichier, indent=4)

def create_white_cards(directory, data):
    with open(join(directory, "white_cards.json"), "w") as fichier:
        cards = list()
        for card in data:
            cards.append(dict(text=card))
        dump(cards, fichier, indent=4)

def main(file):
    with open(file, "r") as fichier:
        data = load(fichier)
        create_black_cards("../mongo/cah/", data["blackCards"])
        create_white_cards("../mongo/cah/", data["whiteCards"])

if __name__ == '__main__':
    main("cah.json")
