"""Filer er sandheden, jf. ADR-0001: biblioteket følger altid filerne i biblioteksmappen."""

import os
from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient

from recipe_reader.app import create_app
from recipe_reader.settings import Settings

WriteFile = Callable[[str, str | bytes], Path]

BROKEN = "---\ntitel: [Pasta med pesto\n---\n\n## Ingredienser\n\n- basilikum\n"


def titles(client: TestClient, **params: str) -> list[str]:
    return [item["titel"] for item in client.get("api/opskrifter", params=params).json()]


def test_a_file_added_outside_the_app_is_seen_in_the_next_call(client: TestClient, write_file: WriteFile) -> None:
    assert titles(client) == []

    write_file("kage.md", "---\ntitel: Kage\n---\n")

    assert titles(client) == ["Kage"]
    assert titles(client, q="kage") == ["Kage"]


def test_a_file_changed_outside_the_app_is_seen_in_the_next_call(client: TestClient, write_file: WriteFile) -> None:
    path = write_file("kage.md", "---\ntitel: Kage\n---\n")
    assert titles(client) == ["Kage"]

    write_file("kage.md", "---\ntitel: Chokoladekage\ntags: [kage]\n---\n")
    os.utime(path, ns=(path.stat().st_atime_ns, path.stat().st_mtime_ns + 1_000_000_000))

    assert titles(client) == ["Chokoladekage"]
    assert titles(client, tag="kage") == ["Chokoladekage"]
    assert client.get("api/opskrifter/kage").json()["titel"] == "Chokoladekage"


def test_a_file_deleted_outside_the_app_disappears(client: TestClient, write_file: WriteFile) -> None:
    path = write_file("kage.md", "---\ntitel: Kage\ntags: [kage]\n---\n")
    assert titles(client) == ["Kage"]

    path.unlink()

    assert titles(client) == []
    assert client.get("api/tags").json() == []
    assert client.get("api/opskrifter/kage").status_code == 404


def test_a_file_that_cannot_be_read_is_listed_and_searchable_by_file_name(
    client: TestClient, write_file: WriteFile
) -> None:
    write_file("pasta-med-pesto.md", BROKEN)

    [item] = client.get("api/opskrifter").json()

    assert item["titel"] == "pasta-med-pesto"
    assert item["advarsel"]
    assert titles(client, q="pesto") == ["pasta-med-pesto"]


def test_a_file_that_cannot_be_read_shows_the_reason_and_the_raw_content(
    client: TestClient, write_file: WriteFile
) -> None:
    write_file("pasta-med-pesto.md", BROKEN)

    recipe = client.get("api/opskrifter/pasta-med-pesto").json()

    assert "YAML i linje 2" in recipe["advarsel"]
    assert recipe["raa"] == BROKEN
    assert recipe["ingredienser"] == []


def test_the_index_is_rebuilt_from_the_files_when_it_is_deleted(
    tmp_path: Path, library_dir: Path, write_file: WriteFile
) -> None:
    settings = Settings(library_dir=library_dir, index_path=tmp_path / "data" / "index.sqlite")
    write_file("a.md", "---\ntitel: Æblekage\nvurdering: 4\ntags: [kage]\n---\n")
    write_file("b.md", "---\ntitel: Boller\noprettet: 2026-01-01\n---\n")
    with TestClient(create_app(settings)) as client:
        before = client.get("api/opskrifter", params={"sortering": "alfabetisk"}).json()

    settings.index_path.unlink()

    with TestClient(create_app(settings)) as client:
        assert client.get("api/opskrifter", params={"sortering": "alfabetisk"}).json() == before
        assert titles(client, tag="kage") == ["Æblekage"]


def test_the_index_is_rebuilt_from_the_files_when_it_is_corrupt(
    tmp_path: Path, library_dir: Path, write_file: WriteFile
) -> None:
    settings = Settings(library_dir=library_dir, index_path=tmp_path / "data" / "index.sqlite")
    write_file("a.md", "---\ntitel: Æblekage\n---\n")
    with TestClient(create_app(settings)) as client:
        before = client.get("api/opskrifter").json()

    settings.index_path.write_bytes(b"ikke en database" * 100)

    with TestClient(create_app(settings)) as client:
        assert client.get("api/opskrifter").json() == before
