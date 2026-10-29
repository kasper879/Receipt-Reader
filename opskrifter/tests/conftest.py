from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from pathlib import Path
from textwrap import dedent

import pytest
from fastapi.testclient import TestClient

from recipe_reader.app import create_app
from recipe_reader.reader import TechnicalError, Udkast
from recipe_reader.settings import Settings


class FakeReader:
    """Falsk aflæser: returnerer foruddefinerede udkast eller en teknisk fejl."""

    def __init__(self) -> None:
        self.udkast: list[dict[str, object]] = []
        self.error: TechnicalError | None = None
        self.calls: list[list[bytes]] = []
        self.on_read: Callable[[], None] | None = None
        """Kaldes, når aflæseren kaldes, så en test kan se, hvad der ligger på disken på det tidspunkt."""

    def read(self, images: list[bytes]) -> list[Udkast]:
        self.calls.append(images)
        if self.on_read:
            self.on_read()
        if self.error:
            raise self.error
        return [Udkast.model_validate(udkast) for udkast in self.udkast]


@pytest.fixture
def library_dir(tmp_path: Path) -> Path:
    path = tmp_path / "opskrifter"
    path.mkdir()
    return path


@pytest.fixture
def fake_reader() -> FakeReader:
    return FakeReader()


@pytest.fixture
def settings(tmp_path: Path, library_dir: Path) -> Settings:
    return Settings(library_dir=library_dir, index_path=tmp_path / "data" / "index.sqlite")


@pytest.fixture
def client(settings: Settings, fake_reader: FakeReader) -> Iterator[TestClient]:
    with TestClient(create_app(settings, reader=fake_reader)) as c:
        yield c


@pytest.fixture
def restart(settings: Settings, fake_reader: FakeReader) -> Callable[[], AbstractContextManager[TestClient]]:
    """Starter appen igen mod samme biblioteksmappe og indeks, som efter en genstart af add-on'en."""
    return lambda: TestClient(create_app(settings, reader=fake_reader))


@pytest.fixture
def write_file(library_dir: Path) -> Callable[[str, str | bytes], Path]:
    """Læg en fil direkte i biblioteksmappen, som via Samba."""

    def write(name: str, content: str | bytes) -> Path:
        path = library_dir / name
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(dedent(content).lstrip(), encoding="utf-8", newline="")
        return path

    return write
