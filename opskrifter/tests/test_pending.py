"""Ventende aflæsning: en teknisk fejl gemmer billederne, så de kan aflæses igen senere."""

import json
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from recipe_reader.app import create_app
from recipe_reader.reader import ConfigurationError, RejectedError, TechnicalError
from recipe_reader.settings import Settings
from tests.conftest import FakeReader
from tests.images import jpeg
from tests.test_new_recipe import BOLLER, start_reading

Restart = Callable[[], AbstractContextManager[TestClient]]


def pending(client: TestClient, fake_reader: FakeReader) -> Any:
    fake_reader.error = TechnicalError("Ingen forbindelse til aflæsningstjenesten")
    response = start_reading(client, jpeg(color="red"), jpeg(color="blue"))
    assert response.status_code == 202
    return response.json()


def test_a_technical_error_gives_a_pending_reading_with_the_images_on_disk(
    client: TestClient, fake_reader: FakeReader, library_dir: Path
) -> None:
    on_disk_when_read: list[list[str]] = []
    fake_reader.on_read = lambda: on_disk_when_read.append(sorted(p.name for p in (library_dir / ".aflaesninger").rglob("*.jpg")))

    reading = pending(client, fake_reader)

    assert on_disk_when_read == [["1.jpg", "2.jpg"]]
    assert reading["status"] == "ventende"
    assert reading["udkast"] == []
    assert reading["fejl"] == "Ingen forbindelse til aflæsningstjenesten"
    assert len(list((library_dir / ".aflaesninger" / reading["id"]).glob("*.jpg"))) == 2
    assert client.get("api/opskrifter").json() == []


def test_pending_readings_are_listed_with_images_and_time(client: TestClient, fake_reader: FakeReader) -> None:
    reading = pending(client, fake_reader)

    [listed] = client.get("api/aflaesninger").json()

    assert listed["id"] == reading["id"]
    assert listed["status"] == "ventende"
    assert len(listed["originalbilleder"]) == 2
    assert abs(datetime.fromisoformat(listed["oprettet"]) - datetime.now()) < timedelta(minutes=1)


def test_retries_wait_longer_each_time(client: TestClient, fake_reader: FakeReader) -> None:
    reading = pending(client, fake_reader)
    first = datetime.fromisoformat(reading["naeste_forsoeg"]) - datetime.now()

    second_attempt = client.post(f"api/aflaesninger/{reading['id']}/proev-igen").json()
    second = datetime.fromisoformat(second_attempt["naeste_forsoeg"]) - datetime.now()

    assert timedelta(seconds=50) < first <= timedelta(minutes=1)
    assert timedelta(minutes=1, seconds=50) < second <= timedelta(minutes=2)
    assert second_attempt["forsoeg"] == 2


def test_retry_now_succeeds_and_gives_drafts(client: TestClient, fake_reader: FakeReader) -> None:
    reading = pending(client, fake_reader)
    fake_reader.error = None
    fake_reader.udkast = [BOLLER]

    retried = client.post(f"api/aflaesninger/{reading['id']}/proev-igen")

    assert retried.status_code == 200
    assert retried.json()["status"] == "udkast"
    assert [draft["titel"] for draft in retried.json()["udkast"]] == ["Boller i karry"]
    assert retried.json()["fejl"] is None
    assert fake_reader.calls[-1] == fake_reader.calls[0]


def test_discard_removes_the_pending_reading_and_its_images(
    client: TestClient, fake_reader: FakeReader, library_dir: Path
) -> None:
    reading = pending(client, fake_reader)

    assert client.delete(f"api/aflaesninger/{reading['id']}").status_code == 200

    assert not (library_dir / ".aflaesninger" / reading["id"]).exists()
    assert client.get("api/aflaesninger").json() == []
    assert client.post(f"api/aflaesninger/{reading['id']}/proev-igen").status_code == 404


def test_a_pending_reading_survives_a_restart(client: TestClient, fake_reader: FakeReader, restart: Restart) -> None:
    reading = pending(client, fake_reader)

    with restart() as restarted:
        assert [r["id"] for r in restarted.get("api/aflaesninger").json()] == [reading["id"]]


def test_a_missing_api_key_keeps_the_images_and_explains_why(client: TestClient, fake_reader: FakeReader) -> None:
    fake_reader.error = ConfigurationError("Angiv en API-nøgle i add-on'ens indstillinger.")

    response = start_reading(client, jpeg())

    assert response.status_code == 202
    assert response.json()["fejl"] == "Angiv en API-nøgle i add-on'ens indstillinger."


def test_pending_readings_are_retried_automatically_in_the_background(
    settings: Settings, fake_reader: FakeReader, library_dir: Path
) -> None:
    with TestClient(create_app(settings, reader=fake_reader, retry_check_seconds=0.05)) as client:
        reading = pending(client, fake_reader)
        # Tiden for næste forsøg er gået: ret den i filen, som om et minut var gået.
        state = library_dir / ".aflaesninger" / reading["id"] / "aflaesning.json"
        data = json.loads(state.read_text(encoding="utf-8"))
        data["naeste_forsoeg"] = (datetime.now() - timedelta(seconds=1)).isoformat()
        state.write_text(json.dumps(data), encoding="utf-8")
        fake_reader.error = None
        fake_reader.udkast = [BOLLER]

        deadline = time.monotonic() + 5
        while client.get(f"api/aflaesninger/{reading['id']}").json()["status"] != "udkast" and time.monotonic() < deadline:
            time.sleep(0.05)

        assert client.get(f"api/aflaesninger/{reading['id']}").json()["status"] == "udkast"


def test_a_reading_interrupted_by_a_restart_is_resumed_at_startup(
    settings: Settings, fake_reader: FakeReader, library_dir: Path
) -> None:
    folder = library_dir / ".aflaesninger" / "20261029-120000-abcd"
    folder.mkdir(parents=True)
    (folder / "1.jpg").write_bytes(jpeg())
    # Appen blev stoppet midt i aflæsningen, før den nåede at sætte tidspunktet for næste forsøg.
    state = {"oprettet": "2026-10-29T12:00:00", "billeder": ["1.jpg"], "status": "ventende", "udkast": []}
    (folder / "aflaesning.json").write_text(json.dumps(state), encoding="utf-8")
    fake_reader.udkast = [BOLLER]

    with TestClient(create_app(settings, reader=fake_reader, retry_check_seconds=0.05)) as client:
        deadline = time.monotonic() + 5
        while client.get(f"api/aflaesninger/{folder.name}").json()["status"] != "udkast" and time.monotonic() < deadline:
            time.sleep(0.05)

        assert client.get(f"api/aflaesninger/{folder.name}").json()["status"] == "udkast"


def test_a_configuration_error_is_not_retried_automatically_but_can_be_retried_now(
    settings: Settings, fake_reader: FakeReader
) -> None:
    with TestClient(create_app(settings, reader=fake_reader, retry_check_seconds=0.05)) as client:
        fake_reader.error = ConfigurationError("Angiv en API-nøgle i add-on'ens indstillinger.")
        reading = start_reading(client, jpeg()).json()

        time.sleep(0.4)

        assert len(fake_reader.calls) == 1
        listed = client.get(f"api/aflaesninger/{reading['id']}").json()
        assert listed["automatisk"] is False
        assert listed["naeste_forsoeg"] is None

        fake_reader.error = None
        fake_reader.udkast = [BOLLER]
        assert client.post(f"api/aflaesninger/{reading['id']}/proev-igen").json()["status"] == "udkast"


def test_a_rejected_reading_is_not_retried_automatically(settings: Settings, fake_reader: FakeReader) -> None:
    with TestClient(create_app(settings, reader=fake_reader, retry_check_seconds=0.05)) as client:
        fake_reader.error = RejectedError("Aflæsningstjenesten afviste billederne.")
        reading = start_reading(client, jpeg()).json()

        time.sleep(0.4)

        assert len(fake_reader.calls) == 1
        assert client.get(f"api/aflaesninger/{reading['id']}").json()["automatisk"] is False
