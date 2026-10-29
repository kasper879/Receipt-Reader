"""Bibliotek: ejer biblioteksmappen og opskrifterne i den."""

import os
import re
import shutil
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path

from . import recipe_format
from .recipe_format import Opskrift

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic"}


TRASH = ".papirkurv"
DELETED = ".slettet"
"""Filen i en mappe i papirkurven, der indeholder tidspunktet for sletningen."""


_SLUG_LETTERS = str.maketrans({"æ": "ae", "ø": "oe", "å": "aa", "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def slugify(title: str) -> str:
    """Et læsbart filnavn ud fra titlen, fx "Mormors æblekage" → "mormors-aeblekage"."""
    text = unicodedata.normalize("NFKD", title.casefold().translate(_SLUG_LETTERS))
    text = "".join(char for char in text if not unicodedata.combining(char))
    slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:60].strip("-")
    return slug or "opskrift"


def _unique(base: str, taken: Callable[[str], bool]) -> str:
    """`base`, eller `base-2`, `base-3` … hvis navnet er optaget."""
    candidate, n = base, 1
    while taken(candidate):
        n += 1
        candidate = f"{base}-{n}"
    return candidate


@dataclass(frozen=True)
class Trashed:
    id: str
    titel: str
    slettet: datetime


class NotFound(Exception):
    """Opskriften findes ikke i biblioteket."""


class HasWarning(Exception):
    """Filen kunne ikke læses korrekt og må derfor kun rettes via Samba."""


def _write(path: Path, text: str) -> None:
    _write_bytes(path, text.encode("utf-8"))


def _write_bytes(path: Path, data: bytes) -> None:
    """Skriver atomisk, så en halv fil aldrig ligger i mappen."""
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_bytes(data)
    os.replace(temp, path)


@dataclass
class Entry:
    """En opskrift i biblioteket. Id'et er filnavnet uden `.md`."""

    id: str
    opskrift: Opskrift


@dataclass(frozen=True)
class LibraryFile:
    """En opskriftsfil, som søgeindekset ser den: id, ændringstid og størrelse."""

    id: str
    mtime_ns: int
    size: int


class Library:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def files(self) -> list[LibraryFile]:
        """Alle opskriftsfiler direkte i mappen. Skjulte undermapper er ikke en del af biblioteket."""
        if not self.directory.is_dir():
            return []
        files = []
        for path in self.directory.glob("*.md"):
            if path.name.startswith(".") or not path.is_file():
                continue
            stat = path.stat()
            files.append(LibraryFile(id=path.stem, mtime_ns=stat.st_mtime_ns, size=stat.st_size))
        return files

    def get(self, recipe_id: str) -> Entry | None:
        path = self._file(f"{recipe_id}.md")
        return self._read(path) if path else None

    def create(self, opskrift: Opskrift, originals: list[Path]) -> str:
        """Gemmer en ny opskrift med et filnavn ud fra titlen og originalbillederne ved siden af.

        Findes filnavnet, får det et nummer bagi. Billederne kopieres, så udkast fra samme
        aflæsning kan dele dem."""
        self.directory.mkdir(parents=True, exist_ok=True)
        recipe_id = _unique(slugify(opskrift.titel or ""), self._taken)
        names = [f"{recipe_id}.{i}{source.suffix.lower()}" for i, source in enumerate(originals, start=1)]
        for source, name in zip(originals, names):
            shutil.copyfile(source, self.directory / name)
        opskrift = replace(opskrift, oprettet=date.today(), originalbilleder=names, retbillede=None, vurdering=None)
        _write(self.directory / f"{recipe_id}.md", recipe_format.write(opskrift))
        return recipe_id

    def set_rating(self, recipe_id: str, rating: int | None) -> None:
        """Skriver vurderingen i filen. Resten af filen er uændret."""
        path = self._writable(recipe_id)
        text = path.read_bytes().decode("utf-8")
        _write(path, recipe_format.set_field(text, "vurdering", rating))

    def set_dish_photo(self, recipe_id: str, jpeg: bytes) -> None:
        """Gemmer retbilledet som `<slug>.ret.jpg` ved siden af filen. Et tidligere retbillede fjernes."""
        path = self._writable(recipe_id)
        name = f"{recipe_id}.ret.jpg"
        _write_bytes(self.directory / name, jpeg)
        self._replace_dish_photo(path, name)

    def remove_dish_photo(self, recipe_id: str) -> None:
        self._replace_dish_photo(self._writable(recipe_id), None)

    def _replace_dish_photo(self, path: Path, name: str | None) -> None:
        opskrift = self._read(path).opskrift
        old = opskrift.retbillede
        _write(path, recipe_format.set_field(path.read_bytes().decode("utf-8"), "retbillede", name))
        # Et originalbillede kan også være valgt som retbillede. Det må ikke slettes.
        if old and old != name and old not in opskrift.originalbilleder and (old_path := self._file(old)):
            old_path.unlink()

    def _writable(self, recipe_id: str) -> Path:
        """Stien til en opskrift, som appen må ændre. En fil med advarsel overskrives aldrig."""
        path = self._file(f"{recipe_id}.md")
        if path is None:
            raise NotFound(recipe_id)
        if self._read(path).opskrift.advarsel:
            raise HasWarning(recipe_id)
        return path

    # ---------------- Papirkurv ----------------
    # Hver slettet opskrift har sin egen undermappe i papirkurven med filen og billederne uændret.

    def trash(self, recipe_id: str) -> str:
        """Flytter opskriften og dens billeder til papirkurven. Det gælder også en fil med advarsel."""
        path = self._file(f"{recipe_id}.md")
        if path is None:
            raise NotFound(recipe_id)
        files = self._recipe_files(path)
        trash = self.directory / TRASH
        folder = trash / _unique(recipe_id, lambda name: (trash / name).exists())
        folder.mkdir(parents=True)
        for file in files:
            os.replace(file, folder / file.name)
        (folder / DELETED).write_text(datetime.now().isoformat(timespec="seconds"), encoding="utf-8")
        return folder.name

    def trashed(self) -> list[Trashed]:
        """Opskrifterne i papirkurven, senest slettet først."""
        trash = self.directory / TRASH
        items = []
        for folder in trash.iterdir() if trash.is_dir() else []:
            md = self._trashed_file(folder.name)
            if md is not None:
                entry = self._read(md)
                deleted = datetime.fromisoformat((folder / DELETED).read_text(encoding="utf-8").strip())
                items.append(Trashed(id=folder.name, titel=entry.opskrift.titel or entry.id, slettet=deleted))
        return sorted(items, key=lambda item: item.slettet, reverse=True)

    def restore(self, trash_id: str) -> str:
        """Flytter opskriften tilbage. Er navnet optaget, får filen og billederne et nummer bagi."""
        md = self._trashed_file(trash_id)
        if md is None:
            raise NotFound(trash_id)
        old_id = md.stem
        new_id = _unique(old_id, self._taken)
        renamed: dict[str, str] = {}
        for file in md.parent.iterdir():
            if file.name == DELETED:
                continue
            name = file.name
            if new_id != old_id and name.startswith(f"{old_id}."):
                name = new_id + name[len(old_id) :]
            if (self.directory / name).exists():
                name = f"{new_id}.{name}"
            if name != file.name:
                renamed[file.name] = name
            os.replace(file, self.directory / name)
        shutil.rmtree(md.parent)
        self._rename_images(new_id, renamed)
        return new_id

    def delete_permanently(self, trash_id: str) -> None:
        md = self._trashed_file(trash_id)
        if md is None:
            raise NotFound(trash_id)
        shutil.rmtree(md.parent)

    def _trashed_file(self, trash_id: str) -> Path | None:
        """Markdown-filen i en mappe i papirkurven. Navne, der peger ud af papirkurven, afvises."""
        folder = self.directory / TRASH / trash_id
        if folder.name != trash_id or trash_id.startswith(".") or not folder.is_dir():
            return None
        return next(folder.glob("*.md"), None)

    def _rename_images(self, recipe_id: str, renamed: dict[str, str]) -> None:
        """Retter billednavnene i frontmatter efter en omdøbning. En fil med advarsel røres ikke."""
        path = self.directory / f"{recipe_id}.md"
        opskrift = self._read(path).opskrift
        if not renamed or opskrift.advarsel:
            return
        text = path.read_bytes().decode("utf-8")
        if opskrift.retbillede in renamed:
            text = recipe_format.set_field(text, "retbillede", renamed[opskrift.retbillede])
        if any(name in renamed for name in opskrift.originalbilleder):
            names = [renamed.get(name, name) for name in opskrift.originalbilleder]
            text = recipe_format.set_field(text, "originalbilleder", names)
        _write(path, text)

    def _recipe_files(self, path: Path) -> list[Path]:
        """Filen selv og dens billeder: dem, der står i frontmatter, og dem med opskriftens slug som præfiks."""
        recipe_id = path.stem
        opskrift = self._read(path).opskrift
        names = {path.name, *opskrift.originalbilleder, *([opskrift.retbillede] if opskrift.retbillede else [])}
        # En anden opskrift som `kage.special.md` ejer selv filer med præfikset `kage.special.`.
        others = [p.stem for p in self.directory.glob(f"{recipe_id}.*.md")]
        for file in self.directory.iterdir():
            name = file.name
            if name.startswith(f"{recipe_id}.") and not name.endswith(".md") and not any(name.startswith(f"{o}.") for o in others):
                names.add(name)
        return [found for name in sorted(names) if (found := self._file(name))]

    def _taken(self, recipe_id: str) -> bool:
        """Om et slug er optaget af en opskrift eller af filer med slugget som præfiks."""
        return (self.directory / f"{recipe_id}.md").exists() or any(
            file.name.startswith(f"{recipe_id}.") for file in self.directory.iterdir()
        )

    def image(self, name: str) -> Path | None:
        """Stien til et billede i biblioteksmappen, eller None hvis det ikke findes der."""
        if Path(name).suffix.lower() not in IMAGE_SUFFIXES:
            return None
        return self._file(name)

    def _file(self, name: str) -> Path | None:
        """En synlig fil direkte i biblioteksmappen. Navne, der peger ud af mappen, afvises."""
        path = self.directory / name
        if path.name != name or name.startswith(".") or not path.is_file():
            return None
        return path

    def _read(self, path: Path) -> Entry:
        data = path.read_bytes()
        try:
            opskrift = recipe_format.parse(data.decode("utf-8"))
        except UnicodeDecodeError:
            opskrift = Opskrift(
                advarsel="Filen er ikke gemt som UTF-8. Gem den igen med UTF-8-tegnsæt.",
                raa=data.decode("utf-8", errors="replace"),
            )
        return Entry(id=path.stem, opskrift=opskrift)
