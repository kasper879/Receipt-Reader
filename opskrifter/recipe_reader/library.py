"""Bibliotek: ejer biblioteksmappen og opskrifterne i den."""

from dataclasses import dataclass
from pathlib import Path

from . import recipe_format
from .recipe_format import Opskrift

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic"}


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
