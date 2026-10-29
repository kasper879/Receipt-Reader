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
    frontmatter, body = _split_frontmatter(text.removeprefix(BOM))
    try:
        meta = yaml.safe_load(frontmatter) or {}
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        # +2: linjerne tælles fra 0 i YAML-fejlen, og frontmatter starter efter linjen '---'.
        where = f" i linje {mark.line + 2}" if mark else ""
        raise _InvalidFile(
            f"Frontmatter er ikke gyldig YAML{where}. Tjek klammer, kolon og anførselstegn."
        ) from error
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


FIELD_ORDER = (
    "titel", "portioner", "forberedelse", "total", "vurdering", "tags", "kilde", "oprettet", "retbillede", "originalbilleder",
)  # fmt: skip


def write(opskrift: Opskrift) -> str:
    """Skriver en opskrift som Markdown. At tolke filen igen giver den samme opskrift."""
    meta: dict[str, object] = {
        "titel": opskrift.titel,
        "portioner": opskrift.portioner,
        "forberedelse": opskrift.forberedelse,
        "total": opskrift.total,
        "vurdering": opskrift.vurdering,
        "tags": opskrift.tags or None,
        "kilde": opskrift.kilde,
        "oprettet": opskrift.oprettet,
        "retbillede": opskrift.retbillede,
        "originalbilleder": opskrift.originalbilleder or None,
    }
    lines = ["---", *(f"{key}: {yaml_value(meta[key])}" for key in FIELD_ORDER if meta[key] is not None), "---", ""]
    for heading, content in _section_contents(opskrift):
        lines += [f"## {heading}", "", *content, *([""] if content else [])]
    return "\n".join(lines).rstrip("\n") + "\n"


EDITABLE_FIELDS = ("titel", "portioner", "forberedelse", "total", "tags", "kilde")
"""Felterne i frontmatter, som rettes i appen. De andre, fx vurdering og billeder, har egne kald."""


def update(text: str, opskrift: Opskrift) -> str:
    """Retter en fil efter en redigeret opskrift. Kun felter, der er ændret, og sektionerne
    Ingredienser, Fremgangsmåde og Noter skrives. Kommentarer, andre felter, tekst før den
    første sektion og andre sektioner bevares, som de står."""
    current = parse(text)
    for key in EDITABLE_FIELDS:
        value = getattr(opskrift, key)
        if value != getattr(current, key):
            text = set_field(text, key, value or None)
    bom = BOM if text.startswith(BOM) else ""
    lines = text.removeprefix(BOM).splitlines(keepends=True)
    newline = "\r\n" if lines and lines[0].endswith("\r\n") else "\n"
    end = next((i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---"), 0) if lines and lines[0].strip() == "---" else -1
    head, body = lines[: end + 1], lines[end + 1 :]

    # Brødteksten delt op i sektioner: teksten før den første `## `, og hver sektion med sin overskrift.
    chunks: list[list[str]] = [[]]
    for line in body:
        if line.startswith("## "):
            chunks.append([])
        chunks[-1].append(line)
    rendered = {heading.lower(): (heading, content) for heading, content in _section_contents(opskrift)}

    def section(heading: str, content: list[str]) -> list[str]:
        return [f"## {heading}{newline}", newline, *(f"{line}{newline}" for line in content), *([newline] if content else [])]

    out = list(chunks[0])
    for chunk in chunks[1:]:
        name = chunk[0][3:].strip().lower()
        if name in rendered:
            out += section(*rendered.pop(name))
        elif name not in KNOWN_SECTIONS:
            out += chunk
    for heading, content in rendered.values():
        if out and out[-1].strip():
            out.append(newline)
        out += section(heading, content)
    result = "".join(head + out).rstrip("\r\n") + newline
    return bom + result


KNOWN_SECTIONS = ("ingredienser", "fremgangsmåde", "noter")


def _section_contents(opskrift: Opskrift) -> list[tuple[str, list[str]]]:
    """Sektionerne, appen skriver, med deres linjer. Noter udelades, når der ingen er."""
    ingredients: list[str] = []
    for group in opskrift.ingredienser:
        if ingredients:
            ingredients.append("")
        if group.gruppe:
            ingredients.append(f"### {group.gruppe}")
        ingredients += [f"- {format_ingredient(line)}" for line in group.linjer]
    sections = [
        ("Ingredienser", ingredients),
        ("Fremgangsmåde", [f"{i}. {step}" for i, step in enumerate(opskrift.trin, start=1)]),
    ]
    if opskrift.noter:
        sections.append(("Noter", opskrift.noter.splitlines()))
    return sections


def format_ingredient(line: Ingredient) -> str:
    """`[mængde] [enhed] navn`, så linjen tolkes til den samme ingrediens igen."""
    parts = [format_quantity(line.maengde) if line.maengde is not None else None, line.enhed, line.navn]
    return " ".join(part for part in parts if part)


def format_quantity(value: Quantity) -> str:
    """Heltal, heltal med unicode-brøk (fx `1½`) eller decimaltal med komma."""
    whole = int(value)
    rest = Fraction(value - whole).limit_denominator(8)
    if rest == 0:
        return str(whole)
    glyph = next((char for char, fraction in UNICODE_FRACTIONS.items() if fraction == rest), None)
    if glyph and abs(float(whole + rest) - value) < 1e-9:
        return f"{whole or ''}{glyph}"
    return f"{value:g}".replace(".", ",")


BOM = "\ufeff"
"""Et byte order mark forrest i filen, som nogle editorer på Windows skriver. Det bevares."""


def set_field(text: str, key: str, value: object) -> str:
    """Sætter ét felt i frontmatter. None fjerner feltet. Resten af filen er byte for byte uændret."""
    if text.startswith(BOM):
        return BOM + set_field(text.removeprefix(BOM), key, value)
    lines = text.splitlines(keepends=True)
    newline = "\r\n" if lines and lines[0].endswith("\r\n") else "\n"
    if not lines or lines[0].strip() != "---":
        head = [f"---{newline}", *([f"{key}: {yaml_value(value)}{newline}"] if value is not None else []), f"---{newline}"]
        return "".join(head) + text
    end = next((i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
    if end is None:
        raise ValueError("Frontmatter er ikke afsluttet med '---'")
    new = [f"{key}: {yaml_value(value)}{newline}"] if value is not None else []
    for i in range(1, end):
        if re.match(rf"^{re.escape(key)}\s*:", lines[i]):
            # Feltets egne linjer: linjen selv og indrykkede linjer eller listepunkter under den.
            stop = i + 1
            while stop < end and re.match(r"^(\s+\S|-\s)", lines[stop]):
                stop += 1
            return "".join(lines[:i] + new + lines[stop:])
    return "".join(lines[:end] + new + lines[end:])


def yaml_value(value: object) -> str:
    """Et felt skrevet som YAML på én linje, fx `4`, `Mormors kogebog` eller `[aftensmad, kage]`."""
    dumped: str = yaml.safe_dump(value, allow_unicode=True, default_flow_style=True, width=10_000)
    return dumped.removesuffix("\n").removesuffix("\n...").strip()


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
