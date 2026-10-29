"""Aflæser: porten mod den eksterne aflæsningstjeneste.

Originalbilleder ind, en liste af udkast ud, eller en teknisk fejl, som betyder,
at aflæsningen skal prøves igen senere. Kontrakten for et udkast: alt er på dansk
og med metriske enheder, felter, der ikke står i originalen, er null, og
ingrediensgrupper bevares. Der er ét udkast pr. opskrift på billederne.
"""

from typing import Annotated, Protocol

from pydantic import BaseModel, Field


class DraftIngredient(BaseModel):
    maengde: Annotated[float, Field(gt=0)] | None = None
    enhed: str | None = None
    navn: str


class DraftGroup(BaseModel):
    gruppe: str | None = None
    linjer: list[DraftIngredient | str] = []
    """En ingrediens som strukturerede felter eller som tekstlinje, fx "2 spsk karry"."""


class Udkast(BaseModel):
    """Et udkast til en opskrift. Felter, der ikke står i originalen, er null."""

    titel: str | None = None
    portioner: Annotated[int, Field(ge=1)] | None = None
    forberedelse: Annotated[int, Field(ge=0)] | None = None
    total: Annotated[int, Field(ge=0)] | None = None
    tags: list[str] = []
    kilde: str | None = None
    ingredienser: list[DraftGroup] = []
    trin: list[str] = []
    noter: str | None = None


class TechnicalError(Exception):
    """Aflæsningen fejlede af tekniske årsager og skal prøves igen senere."""


class ConfigurationError(TechnicalError):
    """Aflæsningstjenesten er ikke sat op, fx mangler API-nøglen. Billederne venter, til det er rettet."""


class Reader(Protocol):
    def read(self, images: list[bytes]) -> list[Udkast]: ...


class UnconfiguredReader:
    def read(self, images: list[bytes]) -> list[Udkast]:
        raise ConfigurationError("Der er ikke sat en aflæsningstjeneste op. Angiv en API-nøgle i add-on'ens indstillinger.")
