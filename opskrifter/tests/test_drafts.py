"""Flere udkast fra én aflæsning, og udkast, der overlever en genstart."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import FakeReader
from tests.images import jpeg
from tests.test_new_recipe import AEBLEKAGE, BOLLER, save, start_reading

Restart = Callable[[], AbstractContextManager[TestClient]]


def two_drafts(client: TestClient, fake_reader: FakeReader) -> Any:
    fake_reader.udkast = [BOLLER, AEBLEKAGE]
    return start_reading(client, jpeg(color="red"), jpeg(color="blue")).json()


def test_a_reading_can_give_two_drafts_that_share_the_original_images(client: TestClient, fake_reader: FakeReader) -> None:
    reading = two_drafts(client, fake_reader)

    assert [(draft["nr"], draft["titel"]) for draft in reading["udkast"]] == [(1, "Boller i karry"), (2, "Mormors æblekage")]
    assert len(reading["originalbilleder"]) == 2
    assert len(fake_reader.calls) == 1


def test_edits_to_a_draft_are_kept(client: TestClient, fake_reader: FakeReader) -> None:
    reading = two_drafts(client, fake_reader)
    edited = {**BOLLER, "titel": "Mormors boller i karry", "ingredienser": [{"gruppe": None, "linjer": ["600 g hakket svinekød"]}]}

    assert client.put(f"api/aflaesninger/{reading['id']}/udkast/1", json=edited).status_code == 200

    [first, second] = client.get(f"api/aflaesninger/{reading['id']}").json()["udkast"]
    assert first["titel"] == "Mormors boller i karry"
    assert first["ingredienser"] == [{"gruppe": None, "linjer": ["600 g hakket svinekød"]}]
    assert second["titel"] == "Mormors æblekage"


def test_save_the_first_draft_and_discard_the_second(
    client: TestClient, fake_reader: FakeReader, library_dir: Path
) -> None:
    reading = two_drafts(client, fake_reader)

    saved = save(client, reading["id"], 1, BOLLER).json()

    assert saved == {"id": "boller-i-karry", "naeste": 2}
    assert [draft["nr"] for draft in client.get(f"api/aflaesninger/{reading['id']}").json()["udkast"]] == [2]
    # Udkast 2 kan stadig se originalbillederne, selv om udkast 1 har fået sine kopier.
    assert client.get(client.get(f"api/aflaesninger/{reading['id']}").json()["originalbilleder"][0]).status_code == 200

    assert client.delete(f"api/aflaesninger/{reading['id']}/udkast/2").json() == {"naeste": None}

    assert [item["titel"] for item in client.get("api/opskrifter").json()] == ["Boller i karry"]
    assert sorted(p.name for p in library_dir.iterdir() if p.is_file()) == [
        "boller-i-karry.1.jpg",
        "boller-i-karry.2.jpg",
        "boller-i-karry.md",
    ]


def test_the_next_draft_wraps_around_to_an_earlier_one(client: TestClient, fake_reader: FakeReader) -> None:
    fake_reader.udkast = [BOLLER, AEBLEKAGE, {**BOLLER, "titel": "Frikadeller"}]
    reading = start_reading(client, jpeg()).json()

    assert client.delete(f"api/aflaesninger/{reading['id']}/udkast/2").json() == {"naeste": 3}
    assert client.delete(f"api/aflaesninger/{reading['id']}/udkast/3").json() == {"naeste": 1}


def test_drafts_survive_a_restart(client: TestClient, fake_reader: FakeReader, restart: Restart) -> None:
    reading = two_drafts(client, fake_reader)
    client.put(f"api/aflaesninger/{reading['id']}/udkast/2", json={**AEBLEKAGE, "titel": "Æblekage"})

    with restart() as restarted:
        readings = restarted.get("api/aflaesninger").json()
        assert [r["id"] for r in readings] == [reading["id"]]
        assert [draft["titel"] for draft in readings[0]["udkast"]] == ["Boller i karry", "Æblekage"]
        assert save(restarted, reading["id"], 2, readings[0]["udkast"][1]).json()["id"] == "aeblekage"


def test_the_reading_folder_is_removed_when_the_last_draft_is_handled(
    client: TestClient, fake_reader: FakeReader, library_dir: Path
) -> None:
    reading = two_drafts(client, fake_reader)
    folder = library_dir / ".aflaesninger" / reading["id"]
    assert folder.is_dir()

    save(client, reading["id"], 2, AEBLEKAGE)
    assert folder.is_dir()
    client.delete(f"api/aflaesninger/{reading['id']}/udkast/1")

    assert not folder.exists()
    assert client.get("api/aflaesninger").json() == []
