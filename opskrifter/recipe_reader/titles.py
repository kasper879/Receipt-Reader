"""Lighedstjek af titel: finder opskrifter i biblioteket, hvis titel ligner et udkasts titel."""

MIN_CONTAINED = 4
"""En titel skal have mindst så mange bogstaver og tal, før den kan ligne en titel, den er en del af.
Ellers ville fx "Is" ligne "Risalamande"."""


def normalize(title: str) -> str:
    """Små bogstaver, kun bogstaver og tal."""
    return "".join(char for char in title.casefold() if char.isalnum())


def similar(title: str, other: str) -> bool:
    """Titlerne er ens, eller den ene indeholder den anden."""
    a, b = normalize(title), normalize(other)
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = sorted((a, b), key=len)
    return len(shorter) >= MIN_CONTAINED and shorter in longer
