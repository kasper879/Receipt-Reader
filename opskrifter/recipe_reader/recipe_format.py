"""Opskriftsformat: tolker en Markdown-fil til en opskrift. Rent, uden IO.

Formatet er beskrevet i specen: YAML-frontmatter efterfulgt af sektionerne
Ingredienser (med valgfrie ###-grupper), Fremgangsmåde og Noter.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from fractions import Fraction

import yaml

UNITS = {
    "g", "kg", "mg", "ml", "cl", "dl", "l",
    "tsk", "spsk", "knsp", "stk", "fed", "dåse", "dåser", "bundt", "pk", "pakke", "pakker",
    "skive", "skiver", "kvist", "kviste", "blad", "blade", "håndfuld", "dråbe", "dråber",
}  # fmt: skip

UNICODE_FRACTIONS = {
    "¼": Fraction(1, 4), "½": Fraction(1, 2), "¾": Fraction(3, 4),
    "⅓": Fraction(1, 3), "⅔": Fraction(2, 3), "⅕": Fraction(1, 5),
    "⅙": Fraction(1, 6), "⅛": Fraction(1, 8), "⅜": Fraction(3, 8),
    "⅝": Fraction(5, 8), "⅞": Fraction(7, 8),
}  # fmt: skip

_FRACTION_CHARS = "".join(UNICODE_FRACTIONS)
# "1 1/2", "1/2", "1½", "1 ½", "½", "1,5", "1.5", "2"
_QUANTITY = re.compile(
    rf"^(?:(?P<whole>\d+)\s+(?P<num>\d+)/(?P<den>[1-9]\d*)"
    rf"|(?P<fnum>\d+)/(?P<fden>[1-9]\d*)"
    rf"|(?:(?P<uwhole>\d+)\s?)?(?P<ufrac>[{_FRACTION_CHARS}])"
    rf"|(?P<decimal>\d+(?:[.,]\d+)?))"
    rf"(?=\s|$)"
)
_STEP = re.compile(r"^(?:\d+[.)]|[-*])\s+")

Quantity = int | float


@dataclass
class Ingredient:
    maengde: Quantity | None
    enhed: str | None
    navn: str


@dataclass
class IngredientGroup:
    gruppe: str | None
    linjer: list[Ingredient] = field(default_factory=list)


@dataclass
class Opskrift:
    titel: str | None = None
    portioner: int | None = None
    forberedelse: int | None = None
    total: int | None = None
    vurdering: int | None = None
    tags: list[str] = field(default_factory=list)
    kilde: str | None = None
    oprettet: date | None = None
    retbillede: str | None = None
    originalbilleder: list[str] = field(default_factory=list)
    ingredienser: list[IngredientGroup] = field(default_factory=list)
    trin: list[str] = field(default_factory=list)
    noter: str | None = None
    advarsel: str | None = None
    """Grunden til, at filen ikke kunne tolkes. Så er resten af felterne tomme."""
    raa: str | None = None
    """Filens rå indhold, når den har en advarsel."""


class _InvalidFile(Exception):
    pass


def parse(text: str) -> Opskrift:
    """Tolker en fil. En fil, der ikke kan tolkes, giver en opskrift med advarsel i stedet for en fejl."""
    try:
        return _parse(text)
    except _InvalidFile as error:
        return Opskrift(advarsel=str(error), raa=text)


def _parse(text: str) -> Opskrift:
    frontmatter, body = _split_frontmatter(text)
    try:
        meta = yaml.safe_load(frontmatter) or {}
    except yaml.YAMLError as error:
        raise _InvalidFile(f"Frontmatter er ikke gyldig YAML: {error}") from error
    if not isinstance(meta, dict):
        raise _InvalidFile("Frontmatter skal bestå af felter som 'titel: …'")
    sections = _sections(body)
    return Opskrift(
        titel=_field(meta, "titel", str),
        portioner=_field(meta, "portioner", int),
        forberedelse=_field(meta, "forberedelse", int),
        total=_field(meta, "total", int),
        vurdering=_rating(meta),
        tags=_list(meta, "tags"),
        kilde=_field(meta, "kilde", str),
        oprettet=_field(meta, "oprettet", date),
        retbillede=_field(meta, "retbillede", str),
        originalbilleder=_list(meta, "originalbilleder"),
        ingredienser=_ingredient_groups(sections.get("ingredienser", [])),
        trin=_steps(sections.get("fremgangsmåde", [])),
        noter="\n".join(sections.get("noter", [])).strip() or None,
    )


def _field[T](meta: dict[str, object], key: str, kind: type[T]) -> T | None:
    value = meta.get(key)
    if value is None or value == "":
        return None
    if kind is str and isinstance(value, (int, float)) and not isinstance(value, bool):
        value = str(value)
    if kind is date:
        value = _date(key, value)
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        raise _InvalidFile(f"Feltet '{key}' har en ugyldig værdi: {value!r}")
    return value


def _rating(meta: dict[str, object]) -> int | None:
    value = _field(meta, "vurdering", int)
    if value is not None and not 1 <= value <= 5:
        raise _InvalidFile(f"Feltet 'vurdering' skal være 1–5: {value!r}")
    return value


def _date(key: str, value: object) -> object:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError as error:
            raise _InvalidFile(f"Feltet '{key}' skal være en dato som 2026-10-21: {value!r}") from error
    return value


def _list(meta: dict[str, object], key: str) -> list[str]:
    value = meta.get(key)
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, (str, int)) for item in value):
        raise _InvalidFile(f"Feltet '{key}' skal være en liste, fx [a, b]")
    return [str(item) for item in value]


def parse_ingredient(line: str) -> Ingredient:
    """Tolker `[mængde] [enhed] navn`. En linje uden mængde er gyldig."""
    line = line.strip()
    match = _QUANTITY.match(line)
    if not match:
        return Ingredient(maengde=None, enhed=None, navn=line)
    rest = line[match.end() :].strip()
    unit, _, name = rest.partition(" ")
    if unit.lower() in UNITS and name.strip():
        return Ingredient(maengde=_quantity(match), enhed=unit.lower(), navn=name.strip())
    return Ingredient(maengde=_quantity(match), enhed=None, navn=rest)


def _quantity(match: re.Match[str]) -> Quantity:
    g = match.groupdict()
    if g["whole"]:
        value = int(g["whole"]) + Fraction(int(g["num"]), int(g["den"]))
    elif g["fnum"]:
        value = Fraction(int(g["fnum"]), int(g["fden"]))
    elif g["ufrac"]:
        value = int(g["uwhole"] or 0) + UNICODE_FRACTIONS[g["ufrac"]]
    else:
        value = Fraction(g["decimal"].replace(",", "."))
    return int(value) if value.denominator == 1 else float(value)


def _split_frontmatter(text: str) -> tuple[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1 :])
    return "", text


def _sections(body: str) -> dict[str, list[str]]:
    """Linjerne under hver `## `-overskrift, med overskriften i små bogstaver som nøgle."""
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in body.splitlines():
        if line.startswith("## "):
            current = sections.setdefault(line[3:].strip().lower(), [])
        elif current is not None:
            current.append(line)
    return sections


def _ingredient_groups(lines: list[str]) -> list[IngredientGroup]:
    groups: list[IngredientGroup] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### "):
            groups.append(IngredientGroup(gruppe=stripped[4:].strip()))
        elif stripped.startswith(("- ", "* ")):
            if not groups:
                groups.append(IngredientGroup(gruppe=None))
            groups[-1].linjer.append(parse_ingredient(stripped[2:]))
    return groups


def _steps(lines: list[str]) -> list[str]:
    steps: list[str] = []
    for line in lines:
        stripped = line.strip()
        if _STEP.match(stripped):
            steps.append(_STEP.sub("", stripped))
        elif stripped and steps:
            steps[-1] += " " + stripped
    return steps
