"""Ny opskrift: upload, aflæsning, gennemsyn og gem, med den falske aflæser."""

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import FakeReader
from tests.images import jpeg, size_of

WriteFile = Callable[[str, str | bytes], Path]

BOLLER: dict[str, Any] = {
    "titel": "Boller i karry",
    "portioner": 4,
    "forberedelse": 30,
    "total": 75,
    "tags": ["aftensmad", "klassiker"],
    "kilde": "Mormors kogebog",
    "ingredienser": [
        {
            "gruppe": "Til kødbollerne",
            "linjer": [
                {"maengde": 500, "enhed": "g", "navn": "hakket svinekød"},
                {"maengde": 1, "enhed": None, "navn": "løg, finthakket"},
                {"maengde": 1.5, "enhed": "dl", "navn": "mælk"},
            ],
        },
        {
            "gruppe": "Til sovsen",
            "linjer": [
                {"maengde": 2, "enhed": "spsk", "navn": "karry"},
                {"maengde": None, "enhed": None, "navn": "salt og peber"},
            ],
        },
    ],
    "trin": ["Bland kødet med løg.", "Form bollerne."],
    "noter": "Mormor kom altid et revet æble i sovsen.",
}

AEBLEKAGE: dict[str, Any] = {
    "titel": "Mormors æblekage",
    "portioner": None,
    "forberedelse": None,
    "total": None,
    "tags": [],
    "kilde": None,
    "ingredienser": [{"gruppe": None, "linjer": [{"maengde": 6, "enhed": None, "navn": "æbler"}, {"maengde": None, "enhed": None, "navn": "kanel"}]}],
    "trin": ["Kog æblerne til grød."],
    "noter": None,
}


def start_reading(client: TestClient, *images: bytes) -> Any:
    files = [("billeder", (f"IMG_{i}.JPG", data, "image/jpeg")) for i, data in enumerate(images, start=1)]
    return client.post("api/aflaesninger", files=files)


def save(client: TestClient, reading_id: str, number: int, draft: dict[str, Any], *, anyway: bool = False) -> Any:
    return client.post(
        f"api/aflaesninger/{reading_id}/udkast/{number}/gem", json={"udkast": draft, "gem_alligevel": anyway}
    )


def test_a_reading_gives_a_draft_with_the_original_images(client: TestClient, fake_reader: FakeReader) -> None:
    fake_reader.udkast = [BOLLER]

    response = start_reading(client, jpeg(color="red"), jpeg(color="blue"))

    assert response.status_code == 200
    reading = response.json()
    assert reading["status"] == "udkast"
    assert len(reading["originalbilleder"]) == 2
    assert [draft["nr"] for draft in reading["udkast"]] == [1]
    assert {key: reading["udkast"][0][key] for key in BOLLER} == BOLLER
    assert len(fake_reader.calls) == 1 and len(fake_reader.calls[0]) == 2
    assert client.get(reading["originalbilleder"][1]).status_code == 200
    assert client.get(f"api/aflaesninger/{reading['id']}").json() == reading


def test_original_images_are_rotated_and_scaled_down(client: TestClient, fake_reader: FakeReader) -> None:
    fake_reader.udkast = [BOLLER]

    reading = start_reading(client, jpeg(4000, 3000, orientation=6)).json()

    assert size_of(client.get(reading["originalbilleder"][0]).content) == (1800, 2400)
    assert size_of(fake_reader.calls[0][0]) == (1800, 2400)


def test_saving_a_draft_writes_the_recipe_and_the_images(
    client: TestClient, fake_reader: FakeReader, library_dir: Path
) -> None:
    fake_reader.udkast = [BOLLER]
    reading = start_reading(client, jpeg(color="red"), jpeg(color="blue")).json()
    first_image = client.get(reading["originalbilleder"][0]).content

    response = save(client, reading["id"], 1, BOLLER)

    assert response.status_code == 200
    assert response.json()["id"] == "boller-i-karry"
    assert (library_dir / "boller-i-karry.md").read_text(encoding="utf-8") == (
        "---\n"
        "titel: Boller i karry\n"
        "portioner: 4\n"
        "forberedelse: 30\n"
        "total: 75\n"
        "tags: [aftensmad, klassiker]\n"
        "kilde: Mormors kogebog\n"
        f"oprettet: {date.today().isoformat()}\n"
        "originalbilleder: [boller-i-karry.1.jpg, boller-i-karry.2.jpg]\n"
        "---\n"
        "\n"
        "## Ingredienser\n"
        "\n"
        "### Til kødbollerne\n"
        "- 500 g hakket svinekød\n"
        "- 1 løg, finthakket\n"
        "- 1½ dl mælk\n"
        "\n"
        "### Til sovsen\n"
        "- 2 spsk karry\n"
        "- salt og peber\n"
        "\n"
        "## Fremgangsmåde\n"
        "\n"
        "1. Bland kødet med løg.\n"
        "2. Form bollerne.\n"
        "\n"
        "## Noter\n"
        "\n"
        "Mormor kom altid et revet æble i sovsen.\n"
    )
    assert (library_dir / "boller-i-karry.1.jpg").read_bytes() == first_image
    assert (library_dir / "boller-i-karry.2.jpg").is_file()
    [item] = client.get("api/opskrifter").json()
    assert item["titel"] == "Boller i karry"
    assert item["oprettet"] == date.today().isoformat()
    assert item["billede"] == "api/billeder/boller-i-karry.1.jpg"


@pytest.mark.parametrize("draft", [BOLLER, AEBLEKAGE], ids=["med grupper", "tomme felter"])
def test_a_saved_recipe_reads_back_as_the_same_recipe(
    client: TestClient, fake_reader: FakeReader, draft: dict[str, Any]
) -> None:
    fake_reader.udkast = [draft]
    reading = start_reading(client, jpeg()).json()

    recipe_id = save(client, reading["id"], 1, draft).json()["id"]
    recipe = client.get(f"api/opskrifter/{recipe_id}").json()

    assert {key: recipe[key] for key in draft} == draft


def test_a_draft_can_be_saved_with_every_field_empty(client: TestClient, fake_reader: FakeReader, library_dir: Path) -> None:
    fake_reader.udkast = [{}]
    reading = start_reading(client, jpeg()).json()

    response = save(client, reading["id"], 1, {})

    assert response.status_code == 200
    recipe_id = response.json()["id"]
    assert recipe_id == "opskrift"
    assert client.get(f"api/opskrifter/{recipe_id}").json()["advarsel"] is None


def test_ingredients_as_text_lines_are_parsed_like_the_file_format(client: TestClient, fake_reader: FakeReader) -> None:
    fake_reader.udkast = [BOLLER]
    reading = start_reading(client, jpeg()).json()
    draft = {**BOLLER, "ingredienser": [{"gruppe": "Dej", "linjer": ["1 1/2 dl mælk", "2 fed hvidløg", "½ citron", "salt"]}]}

    recipe_id = save(client, reading["id"], 1, draft).json()["id"]

    assert client.get(f"api/opskrifter/{recipe_id}").json()["ingredienser"] == [
        {
            "gruppe": "Dej",
            "linjer": [
                {"maengde": 1.5, "enhed": "dl", "navn": "mælk"},
                {"maengde": 2, "enhed": "fed", "navn": "hvidløg"},
                {"maengde": 0.5, "enhed": None, "navn": "citron"},
                {"maengde": None, "enhed": None, "navn": "salt"},
            ],
        }
    ]


def test_similar_titles_are_found(client: TestClient, write_file: WriteFile) -> None:
    write_file("boller-i-karry.md", "---\ntitel: Boller i karry\noprettet: 2026-10-21\n---\n")
    write_file("pasta.md", "---\ntitel: [Pasta\n---\n")

    similar = lambda title: [item["id"] for item in client.get("api/lighed", params={"titel": title}).json()]  # noqa: E731

    assert client.get("api/lighed", params={"titel": "BOLLER I KARRY!"}).json() == [
        {"id": "boller-i-karry", "titel": "Boller i karry", "oprettet": "2026-10-21"}
    ]
    assert similar("Mormors boller i karry") == ["boller-i-karry"]  # den ene indeholder den anden
    assert similar("Boller") == ["boller-i-karry"]
    assert similar("Fiskefrikadeller") == []
    assert similar("Bo") == []  # meget korte titler giver ikke en advarsel
    assert similar("") == []
    assert similar("pasta") == []  # en fil med advarsel har ingen titel at sammenligne med


def test_saving_a_similar_title_is_rejected_unless_confirmed(
    client: TestClient, fake_reader: FakeReader, write_file: WriteFile, library_dir: Path
) -> None:
    write_file("boller-i-karry.md", "---\ntitel: Boller i karry\n---\n")
    fake_reader.udkast = [BOLLER]
    reading = start_reading(client, jpeg()).json()

    rejected = save(client, reading["id"], 1, BOLLER)

    assert rejected.status_code == 409
    assert rejected.json()["lignende"] == [{"id": "boller-i-karry", "titel": "Boller i karry", "oprettet": None}]
    assert sorted(p.name for p in library_dir.glob("*.md")) == ["boller-i-karry.md"]

    accepted = save(client, reading["id"], 1, BOLLER, anyway=True)

    assert accepted.status_code == 200
    assert accepted.json()["id"] == "boller-i-karry-2"
    assert (library_dir / "boller-i-karry-2.1.jpg").is_file()
    assert (library_dir / "boller-i-karry.md").read_text(encoding="utf-8") == "---\ntitel: Boller i karry\n---\n"


def test_after_the_last_draft_is_saved_the_reading_is_cleaned_up(
    client: TestClient, fake_reader: FakeReader, library_dir: Path
) -> None:
    fake_reader.udkast = [BOLLER]
    reading = start_reading(client, jpeg()).json()

    assert save(client, reading["id"], 1, BOLLER).json()["naeste"] is None

    assert client.get(f"api/aflaesninger/{reading['id']}").status_code == 404
    assert [p.name for p in (library_dir / ".aflaesninger").iterdir()] == []


def test_discarding_the_draft_removes_the_reading(client: TestClient, fake_reader: FakeReader, library_dir: Path) -> None:
    fake_reader.udkast = [BOLLER]
    reading = start_reading(client, jpeg()).json()

    response = client.delete(f"api/aflaesninger/{reading['id']}/udkast/1")

    assert response.status_code == 200
    assert response.json() == {"naeste": None}
    assert client.get(f"api/aflaesninger/{reading['id']}").status_code == 404
    assert list(library_dir.glob("*")) == [library_dir / ".aflaesninger"]
    assert client.get("api/opskrifter").json() == []


def test_drafts_and_readings_are_not_part_of_the_library(client: TestClient, fake_reader: FakeReader) -> None:
    fake_reader.udkast = [BOLLER]
    start_reading(client, jpeg())

    assert client.get("api/opskrifter").json() == []
    assert client.get("api/opskrifter", params={"q": "karry"}).json() == []


def test_a_reading_needs_at_least_one_image(client: TestClient) -> None:
    assert client.post("api/aflaesninger", files=[]).status_code == 422


def test_a_file_that_is_not_an_image_is_rejected_before_reading(client: TestClient, fake_reader: FakeReader, library_dir: Path) -> None:
    files = [("billeder", ("noter.txt", b"ikke et billede", "text/plain"))]

    assert client.post("api/aflaesninger", files=files).status_code == 422
    assert fake_reader.calls == []
    assert not (library_dir / ".aflaesninger").exists() or list((library_dir / ".aflaesninger").iterdir()) == []


def test_unknown_readings_and_drafts_give_404(client: TestClient, fake_reader: FakeReader) -> None:
    fake_reader.udkast = [BOLLER]
    reading = start_reading(client, jpeg()).json()

    assert client.get("api/aflaesninger/findes-ikke").status_code == 404
    assert client.get("api/aflaesninger/..").status_code == 404
    assert save(client, reading["id"], 2, BOLLER).status_code == 404
    assert client.delete(f"api/aflaesninger/{reading['id']}/udkast/9").status_code == 404
    assert client.get(f"api/aflaesninger/{reading['id']}/billeder/aflaesning.json").status_code == 404
