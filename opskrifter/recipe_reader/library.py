"""Bibliotek: ejer biblioteksmappen og opskrifterne i den."""

import os
from dataclasses import dataclass
from pathlib import Path

from . import recipe_format
from .recipe_format import Opskrift

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic"}


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
