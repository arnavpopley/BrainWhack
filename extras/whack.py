"""WHACK 26 One Hour Hack: the whack() function. Call it, don't change it.

    from whack import whack
    words = whack()
"""
import random

WORDS = [
    "whack", "hack", "duck", "quack", "goose", "honk", "bug", "feature", "warwick", "oculus",
    "compsoc", "marshall", "wace", "brevan", "howard", "capital", "one", "bloomberg", "netcraft",
    "incident", "io", "pizza", "coffee", "sleep", "deploy", "merge", "conflict", "commit", "push",
    "prod", "segfault", "null", "pointer", "stack", "overflow", "semicolon", "rubber", "demo",
    "pitch", "prize", "midnight", "wifi",
]


def whack() -> list[str]:
    """Writes 1-100 random words to a file called "whack" (one per line) and returns them."""
    words = random.choices(WORDS, k=random.randint(1, 100))
    with open("whack", "w", encoding="utf-8", newline="\n") as file:
        file.write("\n".join(words) + "\n")
    return words
