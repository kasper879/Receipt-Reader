from collections.abc import Callable, Iterator
from pathlib import Path
from textwrap import dedent

import pytest
from fastapi.testclient import TestClient

from recipe_reader.app import create_app
from recipe_reader.reader import Udkast, TechnicalError
from recipe_reader.settings import Settings


class FakeReader:
    """Falsk aflæser: returnerer foruddefinerede udkast eller en teknisk fejl."""

    def __init__(self) -> None:
        self.udkast: list[Udkast] = []
        self.fail = False

    def read(self, images: list[bytes]) -> list[Udkast]:
        if self.fail:
            raise TechnicalError("falsk teknisk fejl")
        return self.udkast


@pytest.fixture
def library_dir(tmp_path: Path) -> Path:
    path = tmp_path / "opskrifter"
    path.mkdir()
    return path


@pytest.fixture
def fake_reader() -> FakeReader:
    return FakeReader()


@pytest.fixture
def client(tmp_path: Path, library_dir: Path, fake_reader: FakeReader) -> Iterator[TestClient]:
    settings = Settings(library_dir=library_dir, index_path=tmp_path / "data" / "index.sqlite")
    with TestClient(create_app(settings, reader=fake_reader)) as c:
        yield c


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
