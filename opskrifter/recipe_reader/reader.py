"""Aflæser: porten mod den eksterne aflæsningstjeneste.

Originalbilleder ind, en liste af udkast ud, eller en teknisk fejl, som betyder,
at aflæsningen skal prøves igen senere. Adapteren mod en rigtig tjeneste kommer
i en senere ticket; indtil da kan en falsk aflæser sættes ind.
"""

from typing import Any, Protocol

Udkast = dict[str, Any]


class TechnicalError(Exception):
    """Aflæsningen fejlede af tekniske årsager og skal prøves igen senere."""


class Reader(Protocol):
    def read(self, images: list[bytes]) -> list[Udkast]: ...


class UnconfiguredReader:
    def read(self, images: list[bytes]) -> list[Udkast]:
        raise TechnicalError("Der er ikke sat en aflæsningstjeneste op")
