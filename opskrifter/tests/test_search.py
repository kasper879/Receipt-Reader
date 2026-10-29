"""Søgning, sortering og tagfilter på biblioteket."""

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

WriteFile = Callable[[str, str | bytes], Path]


def recipe(titel: str, *, extra: str = "", body: str = "") -> str:
    return f"---\ntitel: {titel}\n{extra}---\n\n{body}"


def titles(client: TestClient, **params: str) -> list[str]:
    response = client.get("api/opskrifter", params=params)
    assert response.status_code == 200
    return [item["titel"] for item in response.json()]


@pytest.fixture
def library(write_file: WriteFile) -> None:
    write_file(
        "boller-i-karry.md",
        recipe(
            "Boller i karry",
            extra="tags: [aftensmad, klassiker]\nkilde: Mormors kogebog\noprettet: 2026-10-21\nvurdering: 5\n",
            body="## Ingredienser\n\n- 500 g hakket svinekød\n\n## Noter\n\nMed revet æble.\n",
        ),
    )
    write_file(
        "thai-suppe.md",
        recipe(
            "Thai-suppe",
            extra="tags: [aftensmad, vegetar]\nkilde: Politiken\noprettet: 2026-09-02\nvurdering: 3\n",
            body="## Ingredienser\n\n- 4 dl kokosmælk\n",
        ),
    )
    write_file(
        "aeblekage.md",
        recipe("Æblekage", extra="tags: [kage]\noprettet: 2025-12-24\n", body="## Ingredienser\n\n- 6 æbler\n"),
    )


@pytest.mark.usefixtures("library")
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("karry", ["Boller i karry"]),  # titel
        ("KOKOSMÆLK", ["Thai-suppe"]),  # ingrediens, uden hensyn til store og små bogstaver
        ("vegetar", ["Thai-suppe"]),  # tag
        ("politiken", ["Thai-suppe"]),  # kilde
        ("revet", ["Boller i karry"]),  # noter
    ],
)
def test_search_finds_words_in_each_field(client: TestClient, query: str, expected: list[str]) -> None:
    assert titles(client, q=query) == expected


@pytest.mark.usefixtures("library")
def test_search_matches_the_start_of_words_and_all_words(client: TestClient) -> None:
    assert titles(client, q="kokos") == ["Thai-suppe"]
    assert titles(client, q="aftensmad politiken") == ["Thai-suppe"]
    assert titles(client, q="ingen-ting") == []


@pytest.mark.usefixtures("library")
def test_newest_first_is_the_default(client: TestClient) -> None:
    assert titles(client) == ["Boller i karry", "Thai-suppe", "Æblekage"]
    assert titles(client, sortering="nyeste") == ["Boller i karry", "Thai-suppe", "Æblekage"]


def test_alphabetical_sorting_puts_ae_oe_aa_last(client: TestClient, write_file: WriteFile) -> None:
    for name, title in [("a", "Åbent smørrebrød"), ("b", "Øllebrød"), ("c", "Æbleskiver"), ("d", "Zucchini"), ("e", "agurkesalat")]:
        write_file(f"{name}.md", recipe(title))

    assert titles(client, sortering="alfabetisk") == ["agurkesalat", "Zucchini", "Æbleskiver", "Øllebrød", "Åbent smørrebrød"]


def test_sorting_by_rating_puts_unrated_last_then_alphabetical(client: TestClient, write_file: WriteFile) -> None:
    write_file("a.md", recipe("Citronkage"))
    write_file("b.md", recipe("Brunkager", extra="vurdering: 4\n"))
    write_file("c.md", recipe("Æblekage", extra="vurdering: 5\n"))
    write_file("d.md", recipe("Appelsinkage", extra="vurdering: 4\n"))
    write_file("e.md", recipe("Abrikoskage"))

    assert titles(client, sortering="vurdering") == ["Æblekage", "Appelsinkage", "Brunkager", "Abrikoskage", "Citronkage"]


@pytest.mark.usefixtures("library")
def test_tag_filter(client: TestClient) -> None:
    assert titles(client, tag="aftensmad") == ["Boller i karry", "Thai-suppe"]
    assert titles(client, tag="kage") == ["Æblekage"]
    assert titles(client, tag="findes-ikke") == []


@pytest.mark.usefixtures("library")
def test_tag_filter_combined_with_search(client: TestClient) -> None:
    assert titles(client, tag="aftensmad", q="kokosmælk") == ["Thai-suppe"]
    assert titles(client, tag="kage", q="karry") == []


@pytest.mark.usefixtures("library")
def test_tags_lists_every_tag_in_danish_order(client: TestClient) -> None:
    assert client.get("api/tags").json() == ["aftensmad", "kage", "klassiker", "vegetar"]


def test_unknown_sorting_is_rejected(client: TestClient) -> None:
    assert client.get("api/opskrifter", params={"sortering": "tilfældig"}).status_code == 422


def test_index_lives_in_the_data_folder_not_the_library(
    client: TestClient, write_file: WriteFile, library_dir: Path, tmp_path: Path
) -> None:
    write_file("kage.md", recipe("Kage"))

    assert titles(client) == ["Kage"]
    assert (tmp_path / "data" / "index.sqlite").is_file()
    assert sorted(p.name for p in library_dir.iterdir()) == ["kage.md"]


def test_the_latest_recipe_from_the_same_day_comes_first(client: TestClient, write_file: WriteFile) -> None:
    first = write_file("boller.md", recipe("Boller", extra="oprettet: 2026-10-29\n"))
    second = write_file("aeblekage.md", recipe("Æblekage", extra="oprettet: 2026-10-29\n"))
    os.utime(first, ns=(first.stat().st_atime_ns, 1_700_000_000_000_000_000))
    os.utime(second, ns=(second.stat().st_atime_ns, 1_800_000_000_000_000_000))

    assert titles(client) == ["Æblekage", "Boller"]
