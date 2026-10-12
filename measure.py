"""
Two measures my criteria do not cover, read from a committed run log.

    python measure.py results/run_..._before.md

- fit cards that print a price as "$45.0" instead of "$45"
- outfit suggestions that contain markdown stars (**)
"""

import re
import sys


def blocks(text: str, label: str) -> list[str]:
    return re.findall(rf"{label}:\n\n```\n(.*?)\n```", text, re.S)


def main(path: str) -> None:
    text = open(path, encoding="utf-8").read()
    cards = blocks(text, "Fit card")
    outfits = blocks(text, "Outfit suggestion")
    point_zero = [c for c in cards if re.search(r"\$\d+\.0(?!\d)", c)]
    stars = [o for o in outfits if "**" in o]
    print(path)
    print(f"  fit cards with a price like $45.0: {len(point_zero)} of {len(cards)}")
    print(f"  outfits with markdown stars:       {len(stars)} of {len(outfits)}")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        main(arg)
