#!/usr/bin/env python3
"""Convert a Cards Against Humanity JSON export to MongoDB-ready JSON files.

Downloads the card data from a public source and writes two JSON files
(``black_cards.json`` and ``white_cards.json``) that can be imported
into MongoDB via ``mongoimport``.

Usage::

    python scripts/convert_cah.py [--output-dir mongo/seed]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def create_black_cards(output_dir: Path, data: list[dict]) -> None:
    """Write black cards to a JSON file.

    Args:
        output_dir: Directory to write the file into.
        data: List of black card objects (must have ``text`` and ``pick``).
    """
    output_path = output_dir / "black_cards.json"
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=4, ensure_ascii=False)
    print(f"Wrote {len(data)} black cards to {output_path}")


def create_white_cards(output_dir: Path, data: list[str]) -> None:
    """Write white cards to a JSON file.

    Args:
        output_dir: Directory to write the file into.
        data: List of white card text strings.
    """
    cards = [{"text": card} for card in data]
    output_path = output_dir / "white_cards.json"
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(cards, fh, indent=4, ensure_ascii=False)
    print(f"Wrote {len(cards)} white cards to {output_path}")


def main(input_file: str, output_dir: str) -> None:
    """Read a CAH JSON file and produce MongoDB-importable files.

    Args:
        input_file: Path to the CAH JSON source file.
        output_dir: Directory to write output files into.
    """
    src = Path(input_file)
    dest = Path(output_dir)

    if not src.exists():
        print(f"Error: input file '{src}' not found.", file=sys.stderr)
        sys.exit(1)

    dest.mkdir(parents=True, exist_ok=True)

    with open(src, encoding="utf-8") as fh:
        data = json.load(fh)

    create_black_cards(dest, data["blackCards"])
    create_white_cards(dest, data["whiteCards"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert CAH JSON to MongoDB seed files"
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default="cah.json",
        help="Path to the CAH JSON source file (default: cah.json)",
    )
    parser.add_argument(
        "--output-dir",
        default="mongo/seed",
        help="Directory to write output files (default: mongo/seed)",
    )
    args = parser.parse_args()
    main(args.input_file, args.output_dir)
