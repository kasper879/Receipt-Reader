"""Aflæsningsforløb: originalbilleder, aflæsning, udkast og ventende aflæsninger.

Hver aflæsning har sin egen mappe i den skjulte undermappe `.aflaesninger/` i
biblioteksmappen, så den overlever en genstart og kommer med i HA-backup.
Søgeindekset ignorerer mappen. Originalbillederne gemmes, *før* aflæseren kaldes.
"""

import json
import logging
import secrets
import shutil
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol

from . import images, recipe_format
from .files import write_atomically
from .reader import DraftIngredient, Reader, TechnicalError, Udkast
from .recipe_format import Ingredient, IngredientGroup, Opskrift
from .web_page import PageContent

logger = logging.getLogger(__name__)

FOLDER = ".aflaesninger"
STATE = "aflaesning.json"

RETRY_FIRST = timedelta(minutes=1)
RETRY_MAX = timedelta(hours=6)
"""Ventende aflæsninger prøves igen med stigende interval: 1 min, 2 min, 4 min … højst 6 timer."""

Status = Literal["ventende", "udkast"]


def as_recipe(udkast: Udkast) -> Opskrift:
    """Et udkast som opskrift. Ingredienser som tekstlinjer tolkes med filformatets parser."""
    return Opskrift(
        titel=text_or_none(udkast.titel),
        portioner=udkast.portioner,
        forberedelse=udkast.forberedelse,
        total=udkast.total,
        # Tags skrives med små bogstaver, så "Aftensmad" og "aftensmad" er det samme tag i filteret.
        tags=list(dict.fromkeys(tag.strip().lower() for tag in udkast.tags if tag.strip())),
        kilde=text_or_none(udkast.kilde),
        ingredienser=[
            IngredientGroup(gruppe=text_or_none(group.gruppe), linjer=lines)
            for group in udkast.ingredienser
            if (lines := [line for line in map(_ingredient, group.linjer) if line.navn]) or text_or_none(group.gruppe)
        ],
        trin=[" ".join(step.split()) for step in udkast.trin if step.strip()],
        noter=text_or_none(udkast.noter),
    )


def text_or_none(text: str | None) -> str | None:
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
    """Originalbillederne. Tom, når opskriften hentes fra et link."""
    status: Status
    udkast: list[Draft] = field(default_factory=list)
    forsoeg: int = 0
    naeste_forsoeg: datetime | None = None
    fejl: str | None = None
    """Grunden til, at en ventende aflæsning ikke lykkedes sidst."""
    i_gang: bool = False
    """Om aflæsningen kører lige nu. Gemmes ikke, for en genstart afbryder den."""
    automatisk: bool = True
    link: str | None = None
    """Hjemmesiden, opskriften hentes fra, i stedet for originalbilleder."""
    retbillede: str | None = None
    """Sidens billede af retten, gemt i aflæsningens mappe. Det bliver retbillede, når udkastet gemmes."""
    """Om baggrundsopgaven prøver igen. Ved en ugyldig API-nøgle eller afviste billeder venter den på "prøv nu"."""

    def draft(self, nr: int) -> Draft:
        found = next((draft for draft in self.udkast if draft.nr == nr), None)
        if found is None:
            raise ReadingNotFound(f"{self.id}/{nr}")
        return found

    def next_draft(self, after: int) -> int | None:
        """Nummeret på det næste udkast efter `after`, eller det første, hvis der ikke er flere efter."""
        numbers = [draft.nr for draft in self.udkast if draft.nr != after]
        return next((nr for nr in numbers if nr > after), numbers[0] if numbers else None)


class PageFetcher(Protocol):
    """Henter hjemmesider og billeder fra internettet, jf. web_page.WebFetcher."""

    def page(self, link: str) -> PageContent: ...

    def image(self, link: str) -> bytes: ...


DISH_PHOTO = "ret.jpg"


class Readings:
    def __init__(self, library_dir: Path, reader: Reader, fetcher: PageFetcher) -> None:
        self.directory = library_dir / FOLDER
        self.reader = reader
        self.fetcher = fetcher
        self._lock = threading.RLock()
        self._busy: set[str] = set()
        """Aflæsninger, der bliver aflæst lige nu, så den samme ikke aflæses to gange på én gang."""

    def start(self, images: list[bytes]) -> Reading:
        """Gemmer originalbillederne og starter aflæsningen i baggrunden. Svaret kommer med det samme,
        så en lang aflæsning ikke holder browseren hen. En teknisk fejl giver en ventende aflæsning."""
        now = datetime.now().replace(microsecond=0)
        reading_id = f"{now:%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
        folder = self.directory / reading_id
        folder.mkdir(parents=True)
        names = [f"{i}.jpg" for i in range(1, len(images) + 1)]
        for name, data in zip(names, images):
            (folder / name).write_bytes(data)
        reading = Reading(id=reading_id, oprettet=now, billeder=names, status="ventende")
        with self._lock:
            self._save(reading)
            self._busy.add(reading_id)
        logger.info("Aflæsning %s startet med %d %s", reading_id, len(names), "originalbillede" if len(names) == 1 else "originalbilleder")
        self._in_background(reading)
        return self.get(reading_id)

    def start_from_link(self, link: str) -> Reading:
        """Starter en aflæsning af en opskrift på en hjemmeside, i baggrunden. Siden hentes som en del af aflæsningen,
        så en side, der ikke kan hentes lige nu, bliver en ventende aflæsning."""
        now = datetime.now().replace(microsecond=0)
        reading_id = f"{now:%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
        (self.directory / reading_id).mkdir(parents=True)
        reading = Reading(id=reading_id, oprettet=now, billeder=[], status="ventende", link=link)
        with self._lock:
            self._save(reading)
            self._busy.add(reading_id)
        logger.info("Aflæsning %s startet fra linket %s", reading_id, link)
        self._in_background(reading)
        return self.get(reading_id)

    def retry_in_background(self, reading_id: str) -> Reading:
        """Prøver en ventende aflæsning igen nu, i baggrunden. Er den allerede ved at blive aflæst, sker der ikke mere."""
        with self._lock:
            reading = self.get(reading_id)
            if reading.status != "ventende" or reading_id in self._busy:
                return reading
            self._busy.add(reading_id)
        logger.info("Aflæsning %s prøves igen nu", reading_id)
        self._in_background(reading)
        return self.get(reading_id)

    def retry(self, reading_id: str) -> Reading:
        """Prøver en ventende aflæsning igen og venter på resultatet. Bruges af baggrundsopgaven."""
        with self._lock:
            reading = self.get(reading_id)
            if reading.status != "ventende" or reading_id in self._busy:
                return reading
            self._busy.add(reading_id)
        logger.info("Aflæsning %s prøves igen automatisk", reading_id)
        try:
            return self._perform(reading)
        finally:
            with self._lock:
                self._busy.discard(reading_id)

    def _in_background(self, reading: Reading) -> None:
        """Aflæser i en tråd. Aflæsningen er markeret som i gang, til tråden er færdig."""

        def run() -> None:
            try:
                self._perform(reading)
            except Exception:
                logger.exception("Aflæsning %s fejlede uventet", reading.id)
            finally:
                with self._lock:
                    self._busy.discard(reading.id)

        threading.Thread(target=run, name=f"aflaesning-{reading.id}", daemon=True).start()

    def due(self, now: datetime) -> list[str]:
        """Ventende aflæsninger, der skal prøves igen automatisk nu.

        En aflæsning uden tidspunkt for næste forsøg blev afbrudt, fx af en genstart, og genoptages straks."""
        with self._lock:
            busy = set(self._busy)
        return [
            r.id
            for r in self.list()
            if r.status == "ventende"
            and r.automatisk
            and r.id not in busy
            and (r.naeste_forsoeg is None or r.naeste_forsoeg <= now)
        ]

    def _perform(self, reading: Reading) -> Reading:
        """Kalder aflæseren og gemmer resultatet: udkast, eller tidspunktet for næste forsøg."""
        started = time.monotonic()
        try:
            drafts = self._read_page(reading) if reading.link else self.reader.read(self._originals(reading))
        except TechnicalError as error:
            reading.forsoeg += 1
            reading.fejl = str(error)
            reading.automatisk = error.retry_automatically
            delay = min(RETRY_FIRST * 2 ** (reading.forsoeg - 1), RETRY_MAX)
            reading.naeste_forsoeg = datetime.now().replace(microsecond=0) + delay if reading.automatisk else None
            next_attempt = f"Næste forsøg kl. {reading.naeste_forsoeg:%H:%M}." if reading.naeste_forsoeg else "Venter på, at du trykker \"prøv igen\"."
            logger.warning(
                "Aflæsning %s lykkedes ikke (forsøg %d): %s %s (efter %.0f s)",
                reading.id, reading.forsoeg, error, next_attempt, time.monotonic() - started,
            )
        else:
            titles = ", ".join(udkast.titel or "uden titel" for udkast in drafts)
            logger.info(
                "Aflæsning %s gav %d udkast på %.0f s: %s", reading.id, len(drafts), time.monotonic() - started, titles or "ingen opskrifter"
            )
            reading.status = "udkast"
            reading.udkast = [Draft(nr=i, udkast=udkast) for i, udkast in enumerate(drafts, start=1)]
            reading.fejl = reading.naeste_forsoeg = None
            reading.automatisk = True
            if not reading.udkast:
                reading.fejl = "Aflæsningen fandt ingen opskrifter på billederne."
        with self._lock:
            if (self.directory / reading.id).is_dir():
                self._save(reading)
        return reading

    def _originals(self, reading: Reading) -> list[bytes]:
        return [(self.directory / reading.id / name).read_bytes() for name in reading.billeder]

    def _read_page(self, reading: Reading) -> list[Udkast]:
        """Henter siden og dens billede af retten og læser opskriften. Et billede, der ikke kan hentes, springes over."""
        assert reading.link
        page = self.fetcher.page(reading.link)
        if page.image_url and not reading.retbillede:
            try:
                photo = images.prepare(self.fetcher.image(page.image_url), images.DISH_PHOTO_SIZE)
                write_atomically(self.directory / reading.id / DISH_PHOTO, photo)
                reading.retbillede = DISH_PHOTO
            except (TechnicalError, images.InvalidImage, KeyError) as error:
                logger.info("Billedet af retten på %s kunne ikke hentes: %s", page.url, error)
        logger.info("Siden %s hentet (%d tegn tekst, %d opskrifter som data)", page.url, len(page.text), len(page.recipes))
        return self.reader.read_page(page)

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
            # Under låsen, så filen ikke læses, mens baggrundstråden skriver den.
            with self._lock:
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
            automatisk=data.get("automatisk", True),
            link=data.get("link"),
            retbillede=data.get("retbillede"),
            i_gang=reading_id in self._busy,
        )

    def dish_photo(self, reading_id: str, nr: int, longest_side: int) -> bytes | None:
        """Fotoet af retten: sidens billede ved et link, ellers udkastets område på originalbillederne,
        beskåret som JPEG. None, hvis der ikke er et."""
        reading = self.get(reading_id)
        if reading.retbillede:
            return self.image(reading_id, reading.retbillede).read_bytes()
        area = reading.draft(nr).udkast.retbillede_omraade
        if area is None or area.billede > len(reading.billeder):
            return None
        source = self.image(reading_id, reading.billeder[area.billede - 1]).read_bytes()
        try:
            return images.crop(source, (area.venstre, area.top, area.hoejre, area.bund), longest_side)
        except images.InvalidImage:
            return None

    def image(self, reading_id: str, name: str) -> Path:
        reading = self.get(reading_id)
        if name not in reading.billeder and name != reading.retbillede:
            raise ReadingNotFound(f"{reading_id}/{name}")
        return self._folder(reading_id) / name

    def update_draft(self, reading_id: str, nr: int, udkast: Udkast) -> None:
        """Gemmer rettelser i et udkast midlertidigt under gennemsynet."""
        with self._lock:
            reading = self.get(reading_id)
            draft = reading.draft(nr)
            # Frontenden kender ikke området for retbilledet, så det beholdes fra aflæsningen.
            draft.udkast = udkast.model_copy(update={"retbillede_omraade": udkast.retbillede_omraade or draft.udkast.retbillede_omraade})
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
            "automatisk": reading.automatisk,
            "link": reading.link,
            "retbillede": reading.retbillede,
        }
        write_atomically(self.directory / reading.id / STATE, json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
