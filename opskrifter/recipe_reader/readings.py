"""Aflæsningsforløb: originalbilleder, aflæsning, udkast og ventende aflæsninger.

Hver aflæsning har sin egen mappe i den skjulte undermappe `.aflaesninger/` i
biblioteksmappen, så den overlever en genstart og kommer med i HA-backup.
Søgeindekset ignorerer mappen. Originalbillederne gemmes, *før* aflæseren kaldes.
"""

import json
import os
import secrets
import shutil
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from . import recipe_format
from .reader import DraftGroup, DraftIngredient, Reader, TechnicalError, Udkast
from .recipe_format import Ingredient, IngredientGroup, Opskrift

FOLDER = ".aflaesninger"
STATE = "aflaesning.json"

RETRY_FIRST = timedelta(minutes=1)
RETRY_MAX = timedelta(hours=6)
"""Ventende aflæsninger prøves igen med stigende interval: 1 min, 2 min, 4 min … højst 6 timer."""

Status = Literal["ventende", "udkast"]


def as_recipe(udkast: Udkast) -> Opskrift:
    """Et udkast som opskrift. Ingredienser som tekstlinjer tolkes med filformatets parser."""
    return Opskrift(
        titel=blank(udkast.titel),
        portioner=udkast.portioner,
        forberedelse=udkast.forberedelse,
        total=udkast.total,
        tags=[tag.strip() for tag in udkast.tags if tag.strip()],
        kilde=blank(udkast.kilde),
        ingredienser=[
            IngredientGroup(gruppe=blank(group.gruppe), linjer=lines)
            for group in udkast.ingredienser
            if (lines := [line for line in map(_ingredient, group.linjer) if line.navn]) or blank(group.gruppe)
        ],
        trin=[" ".join(step.split()) for step in udkast.trin if step.strip()],
        noter=blank(udkast.noter),
    )


def as_draft(opskrift: Opskrift) -> Udkast:
    """En gemt opskrift som udkast, så den kan redigeres i gennemsynets opsætning."""
    return Udkast(
        titel=opskrift.titel,
        portioner=opskrift.portioner,
        forberedelse=opskrift.forberedelse,
        total=opskrift.total,
        tags=opskrift.tags,
        kilde=opskrift.kilde,
        ingredienser=[
            DraftGroup(gruppe=group.gruppe, linjer=[DraftIngredient(**asdict(line)) for line in group.linjer])
            for group in opskrift.ingredienser
        ],
        trin=opskrift.trin,
        noter=opskrift.noter,
    )


def blank(text: str | None) -> str | None:
    """Tekst uden mellemrum før og efter. Tom tekst er "ikke angivet"."""
    return (text or "").strip() or None


def _ingredient(line: DraftIngredient | str) -> Ingredient:
    if isinstance(line, str):
        return recipe_format.parse_ingredient(line)
    quantity = line.maengde
    if quantity is not None and float(quantity).is_integer():
        quantity = int(quantity)
    return Ingredient(maengde=quantity, enhed=(line.enhed or "").strip() or None, navn=" ".join(line.navn.split()))


class ReadingNotFound(Exception):
    """Aflæsningen eller udkastet findes ikke."""


@dataclass
class Draft:
    nr: int
    udkast: Udkast


@dataclass
class Reading:
    id: str
    oprettet: datetime
    billeder: list[str]
    status: Status
    udkast: list[Draft] = field(default_factory=list)
    forsoeg: int = 0
    naeste_forsoeg: datetime | None = None
    fejl: str | None = None
    """Grunden til, at en ventende aflæsning ikke lykkedes sidst."""

    def draft(self, nr: int) -> Draft:
        found = next((draft for draft in self.udkast if draft.nr == nr), None)
        if found is None:
            raise ReadingNotFound(f"{self.id}/{nr}")
        return found

    def next_draft(self, after: int) -> int | None:
        """Nummeret på det næste udkast efter `after`, eller det første, hvis der ikke er flere efter."""
        numbers = [draft.nr for draft in self.udkast if draft.nr != after]
        return next((nr for nr in numbers if nr > after), numbers[0] if numbers else None)


class Readings:
    def __init__(self, library_dir: Path, reader: Reader) -> None:
        self.directory = library_dir / FOLDER
        self.reader = reader
        self._lock = threading.RLock()
        self._busy: set[str] = set()
        """Aflæsninger, der bliver aflæst lige nu, så den samme ikke aflæses to gange på én gang."""

    def start(self, images: list[bytes]) -> Reading:
        """Gemmer originalbillederne og aflæser dem. En teknisk fejl giver en ventende aflæsning."""
        now = datetime.now().replace(microsecond=0)
        reading_id = f"{now:%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
        folder = self.directory / reading_id
        with self._lock:
            self._busy.add(reading_id)
        try:
            folder.mkdir(parents=True)
            names = [f"{i}.jpg" for i in range(1, len(images) + 1)]
            for name, data in zip(names, images):
                (folder / name).write_bytes(data)
            reading = Reading(id=reading_id, oprettet=now, billeder=names, status="ventende")
            self._save(reading)
            return self._read(reading)
        finally:
            with self._lock:
                self._busy.discard(reading_id)

    def retry(self, reading_id: str) -> Reading:
        """Prøver en ventende aflæsning igen nu. Er den allerede ved at blive aflæst, sker der ikke mere."""
        with self._lock:
            reading = self.get(reading_id)
            if reading.status != "ventende" or reading_id in self._busy:
                return reading
            self._busy.add(reading_id)
        try:
            return self._read(reading)
        finally:
            with self._lock:
                self._busy.discard(reading_id)

    def due(self, now: datetime) -> list[str]:
        """Ventende aflæsninger, der skal prøves igen automatisk nu.

        En aflæsning uden tidspunkt for næste forsøg blev afbrudt, fx af en genstart, og genoptages straks."""
        return [
            r.id
            for r in self.list()
            if r.status == "ventende" and r.id not in self._busy and (r.naeste_forsoeg is None or r.naeste_forsoeg <= now)
        ]

    def _read(self, reading: Reading) -> Reading:
        images = [(self.directory / reading.id / name).read_bytes() for name in reading.billeder]
        try:
            drafts = self.reader.read(images)
        except TechnicalError as error:
            reading.forsoeg += 1
            reading.fejl = str(error)
            delay = min(RETRY_FIRST * 2 ** (reading.forsoeg - 1), RETRY_MAX)
            reading.naeste_forsoeg = datetime.now().replace(microsecond=0) + delay
        else:
            reading.status = "udkast"
            reading.udkast = [Draft(nr=i, udkast=udkast) for i, udkast in enumerate(drafts, start=1)]
            reading.fejl = reading.naeste_forsoeg = None
            if not reading.udkast:
                reading.fejl = "Aflæsningen fandt ingen opskrifter på billederne."
        with self._lock:
            if (self.directory / reading.id).is_dir():
                self._save(reading)
        return reading

    def list(self) -> list[Reading]:
        """Alle aflæsninger, ældste først."""
        if not self.directory.is_dir():
            return []
        readings = []
        for folder in sorted(self.directory.iterdir()):
            try:
                readings.append(self.get(folder.name))
            except ReadingNotFound:
                continue
        return readings

    def get(self, reading_id: str) -> Reading:
        state = self._folder(reading_id) / STATE
        try:
            data = json.loads(state.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise ReadingNotFound(reading_id) from error
        return Reading(
            id=reading_id,
            oprettet=datetime.fromisoformat(data["oprettet"]),
            billeder=data["billeder"],
            status=data["status"],
            udkast=[Draft(nr=d["nr"], udkast=Udkast.model_validate(d["udkast"])) for d in data["udkast"]],
            forsoeg=data.get("forsoeg", 0),
            naeste_forsoeg=datetime.fromisoformat(data["naeste_forsoeg"]) if data.get("naeste_forsoeg") else None,
            fejl=data.get("fejl"),
        )

    def image(self, reading_id: str, name: str) -> Path:
        reading = self.get(reading_id)
        if name not in reading.billeder:
            raise ReadingNotFound(f"{reading_id}/{name}")
        return self._folder(reading_id) / name

    def update_draft(self, reading_id: str, nr: int, udkast: Udkast) -> None:
        """Gemmer rettelser i et udkast midlertidigt under gennemsynet."""
        with self._lock:
            reading = self.get(reading_id)
            reading.draft(nr).udkast = udkast
            self._save(reading)

    def remove_draft(self, reading_id: str, nr: int) -> int | None:
        """Fjerner et udkast, der er gemt eller kasseret. Er det det sidste, fjernes hele aflæsningen.

        Returnerer nummeret på det næste udkast, eller None, når der ikke er flere."""
        with self._lock:
            reading = self.get(reading_id)
            reading.draft(nr)
            following = reading.next_draft(nr)
            reading.udkast = [draft for draft in reading.udkast if draft.nr != nr]
            if reading.udkast:
                self._save(reading)
            else:
                self.discard(reading_id)
            return following

    def discard(self, reading_id: str) -> None:
        """Sletter aflæsningen og dens originalbilleder."""
        with self._lock:
            folder = self._folder(reading_id)
            if not (folder / STATE).is_file():
                raise ReadingNotFound(reading_id)
            shutil.rmtree(folder)

    def _folder(self, reading_id: str) -> Path:
        folder = self.directory / reading_id
        if folder.name != reading_id or reading_id.startswith("."):
            raise ReadingNotFound(reading_id)
        return folder

    def _save(self, reading: Reading) -> None:
        data: dict[str, Any] = {
            "oprettet": reading.oprettet.isoformat(),
            "billeder": reading.billeder,
            "status": reading.status,
            "udkast": [{"nr": d.nr, "udkast": d.udkast.model_dump()} for d in reading.udkast],
            "forsoeg": reading.forsoeg,
            "naeste_forsoeg": reading.naeste_forsoeg.isoformat() if reading.naeste_forsoeg else None,
            "fejl": reading.fejl,
        }
        state = self.directory / reading.id / STATE
        temp = state.with_name(f".{STATE}.tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, state)
