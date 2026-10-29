"""Vurdering: sæt, ændr og fjern. Kun feltet i filen ændres."""

from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient

WriteFile = Callable[[str, str | bytes], Path]

KAGE = "---\ntitel: Kage\ntags: [kage]\n---\n\n## Ingredienser\n\n- 3 æg\n"


def set_rating(client: TestClient, recipe_id: str, rating: int | None) -> int:
    return client.put(f"api/opskrifter/{recipe_id}/vurdering", json={"vurdering": rating}).status_code


def test_set_rating_writes_the_field_and_leaves_the_rest_of_the_file(
    client: TestClient, write_file: WriteFile
) -> None:
    path = write_file("kage.md", KAGE)

    assert set_rating(client, "kage", 4) == 200

    assert path.read_bytes() == b"---\ntitel: Kage\ntags: [kage]\nvurdering: 4\n---\n\n## Ingredienser\n\n- 3 \xc3\xa6g\n"
    assert client.get("api/opskrifter/kage").json()["vurdering"] == 4
    assert client.get("api/opskrifter").json()[0]["vurdering"] == 4


def test_change_rating_replaces_the_line_in_place(client: TestClient, write_file: WriteFile) -> None:
    path = write_file("kage.md", "---\ntitel: Kage\nvurdering: 2\ntags: [kage]\n---\n\nTekst\n")

    assert set_rating(client, "kage", 5) == 200

    assert path.read_text(encoding="utf-8") == "---\ntitel: Kage\nvurdering: 5\ntags: [kage]\n---\n\nTekst\n"


def test_remove_rating_removes_the_field(client: TestClient, write_file: WriteFile) -> None:
    path = write_file("kage.md", "---\ntitel: Kage\nvurdering: 3\ntags: [kage]\n---\n\nTekst\n")

    assert set_rating(client, "kage", None) == 200

    assert path.read_text(encoding="utf-8") == "---\ntitel: Kage\ntags: [kage]\n---\n\nTekst\n"
    assert client.get("api/opskrifter/kage").json()["vurdering"] is None


def test_windows_line_endings_are_kept(client: TestClient, write_file: WriteFile) -> None:
    path = write_file("kage.md", b"---\r\ntitel: Kage\r\n---\r\n\r\nTekst\r\n")

    assert set_rating(client, "kage", 1) == 200

    assert path.read_bytes() == b"---\r\ntitel: Kage\r\nvurdering: 1\r\n---\r\n\r\nTekst\r\n"


def test_a_file_without_frontmatter_gets_one(client: TestClient, write_file: WriteFile) -> None:
    path = write_file("kage.md", "## Ingredienser\n\n- 3 æg\n")

    assert set_rating(client, "kage", 5) == 200

    assert path.read_text(encoding="utf-8") == "---\nvurdering: 5\n---\n## Ingredienser\n\n- 3 æg\n"


def test_sorting_by_rating_follows_the_change(client: TestClient, write_file: WriteFile) -> None:
    write_file("a.md", "---\ntitel: Abekat\nvurdering: 3\n---\n")
    write_file("b.md", "---\ntitel: Banankage\n---\n")

    set_rating(client, "b", 5)

    titles = [item["titel"] for item in client.get("api/opskrifter", params={"sortering": "vurdering"}).json()]
    assert titles == ["Banankage", "Abekat"]


def test_rating_must_be_one_to_five(client: TestClient, write_file: WriteFile) -> None:
    path = write_file("kage.md", KAGE)

    assert set_rating(client, "kage", 0) == 422
    assert set_rating(client, "kage", 6) == 422
    assert path.read_text(encoding="utf-8") == KAGE


def test_rating_an_unknown_recipe_gives_404(client: TestClient) -> None:
    assert set_rating(client, "findes-ikke", 3) == 404


def test_a_file_that_cannot_be_read_is_never_changed(client: TestClient, write_file: WriteFile) -> None:
    broken = "---\ntitel: [Pasta\n---\n"
    path = write_file("pasta.md", broken)

    response = client.put("api/opskrifter/pasta/vurdering", json={"vurdering": 4})

    assert response.status_code == 409
    assert path.read_text(encoding="utf-8") == broken
