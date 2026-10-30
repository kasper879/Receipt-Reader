"""Aflæser: porten mod den eksterne aflæsningstjeneste.

Originalbilleder ind, en liste af udkast ud, eller en teknisk fejl, som betyder,
at aflæsningen skal prøves igen senere. Kontrakten for et udkast: alt er på dansk
og med metriske enheder, felter, der ikke står i originalen, er null, og
ingrediensgrupper bevares. Der er ét udkast pr. opskrift på billederne.
"""

from typing import TYPE_CHECKING, Annotated, Protocol

from pydantic import BaseModel, Field, model_validator

if TYPE_CHECKING:
    from .web_page import PageContent


class DraftIngredient(BaseModel):
    maengde: Annotated[float, Field(gt=0)] | None = None
    enhed: str | None = None
    navn: str


class DraftGroup(BaseModel):
    gruppe: str | None = None
    linjer: list[DraftIngredient | str] = []
    """En ingrediens som strukturerede felter eller som tekstlinje, fx "2 spsk karry"."""


Fraction = Annotated[float, Field(ge=0, le=1)]

MIN_AREA = 0.05
"""Den mindste bredde og højde af et retbillede, som brøkdel af originalbilledet."""


class DishPhotoArea(BaseModel):
    """Hvor på originalbillederne der er et foto af den færdige ret: billedets nummer (fra 1) og
    området som brøkdele af billedets bredde og højde, målt fra øverste venstre hjørne."""

    billede: Annotated[int, Field(ge=1)]
    venstre: Fraction
    top: Fraction
    hoejre: Fraction
    bund: Fraction

    @model_validator(mode="after")
    def _has_size(self) -> "DishPhotoArea":
        if self.hoejre - self.venstre < MIN_AREA or self.bund - self.top < MIN_AREA:
            raise ValueError("Området for retbilledet er for lille")
        return self


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
    retbillede_omraade: DishPhotoArea | None = None
    """Et foto af retten på originalbillederne, som bliver retbillede, når udkastet gemmes."""


class TechnicalError(Exception):
    """Aflæsningen fejlede af tekniske årsager og skal prøves igen senere."""

    retry_automatically = True
    """Om baggrundsopgaven skal prøve igen. Ellers venter billederne, til brugeren trykker "prøv nu"."""


class ConfigurationError(TechnicalError):
    """Aflæsningstjenesten er ikke sat op, fx mangler API-nøglen. Billederne venter, til det er rettet."""

    retry_automatically = False


class RejectedError(TechnicalError):
    """Aflæsningstjenesten kunne ikke bruge billederne, og det samme forsøg vil fejle igen."""

    retry_automatically = False


class Reader(Protocol):
    def read(self, images: list[bytes]) -> list[Udkast]: ...

    def read_page(self, page: "PageContent") -> list[Udkast]:
        """Læser en opskrift fra en hjemmesides indhold. Samme kontrakt som for billeder."""
        ...


class UnconfiguredReader:
    def read(self, images: list[bytes]) -> list[Udkast]:
        raise ConfigurationError("Der er ikke sat en aflæsningstjeneste op. Angiv en API-nøgle i add-on'ens indstillinger.")

    def read_page(self, page: "PageContent") -> list[Udkast]:
        return self.read([])
