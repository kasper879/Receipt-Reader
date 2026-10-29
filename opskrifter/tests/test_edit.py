"""Redigér en gemt opskrift: samme fil, samme filnavn, og originalbilleder kan tilføjes."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from tests.images import jpeg

WriteFile = Callable[[str, str | bytes], Path]

BOLLER = """---
titel: Boller i karry
portioner: 4
vurdering: 5
tags: [aftensmad]
kilde: Mormors kogebog
oprettet: 2026-10-21
retbillede: boller-i-karry.ret.jpg
originalbilleder: [boller-i-karry.1.jpg]
---

## Ingredienser

### Til sovsen
- 2 spsk karry

## Fremgangsmåde

1. Lav sovsen.
"""


def update(client: TestClient, recipe_id: str, draft: dict[str, Any], *, anyway: bool = False) -> Any:
    return client.put(f"api/opskrifter/{recipe_id}", json={"udkast": draft, "gem_alligevel": anyway})


def as_draft(recipe: dict[str, Any]) -> dict[str, Any]:
    fields = ["titel", "portioner", "forberedelse", "total", "tags", "kilde", "ingredienser", "trin", "noter"]
    return {key: recipe[key] for key in fields}


def test_update_changes_the_file_in_place_with_the_same_file_name(
    client: TestClient, write_file: WriteFile, library_dir: Path
) -> None:
    write_file("boller-i-karry.md", BOLLER)
    draft = as_draft(client.get("api/opskrifter/boller-i-karry").json())
    draft["titel"] = "Mormors boller i karry"
    draft["ingredienser"][0]["linjer"].append("salt og peber")
    draft["trin"].append("Server med ris.")

    response = update(client, "boller-i-karry", draft)

    assert response.status_code == 200
    assert response.json()["id"] == "boller-i-karry"
    assert sorted(p.name for p in library_dir.glob("*.md")) == ["boller-i-karry.md"]
    assert (library_dir / "boller-i-karry.md").read_text(encoding="utf-8") == (
        "---\n"
        "titel: Mormors boller i karry\n"
        "portioner: 4\n"
        "vurdering: 5\n"
        "tags: [aftensmad]\n"
        "kilde: Mormors kogebog\n"
        "oprettet: 2026-10-21\n"
        "retbillede: boller-i-karry.ret.jpg\n"
        "originalbilleder: [boller-i-karry.1.jpg]\n"
        "---\n"
        "\n"
        "## Ingredienser\n"
        "\n"
        "### Til sovsen\n"
        "- 2 spsk karry\n"
        "- salt og peber\n"
        "\n"
        "## Fremgangsmåde\n"
        "\n"
        "1. Lav sovsen.\n"
        "2. Server med ris.\n"
    )
    assert [item["titel"] for item in client.get("api/opskrifter", params={"q": "mormors"}).json()] == ["Mormors boller i karry"]


def test_fields_that_are_not_edited_are_unchanged(client: TestClient, write_file: WriteFile) -> None:
    write_file("boller-i-karry.md", BOLLER)
    before = client.get("api/opskrifter/boller-i-karry").json()

    update(client, "boller-i-karry", as_draft(before))

    assert client.get("api/opskrifter/boller-i-karry").json() == before


def test_a_title_similar_to_another_recipe_is_rejected_unless_confirmed(client: TestClient, write_file: WriteFile) -> None:
    write_file("boller-i-karry.md", BOLLER)
    write_file("frikadeller.md", "---\ntitel: Frikadeller\n---\n")
    draft = {**as_draft(client.get("api/opskrifter/boller-i-karry").json()), "titel": "Frikadeller med sovs"}

    rejected = update(client, "boller-i-karry", draft)

    assert rejected.status_code == 409
    assert [item["id"] for item in rejected.json()["lignende"]] == ["frikadeller"]
    assert client.get("api/opskrifter/boller-i-karry").json()["titel"] == "Boller i karry"
    assert update(client, "boller-i-karry", draft, anyway=True).status_code == 200


def test_the_recipe_itself_does_not_count_as_a_similar_title(client: TestClient, write_file: WriteFile) -> None:
    write_file("boller-i-karry.md", BOLLER)
    draft = as_draft(client.get("api/opskrifter/boller-i-karry").json())

    assert update(client, "boller-i-karry", draft).status_code == 200
    assert client.get("api/lighed", params={"titel": "Boller i karry", "undtagen": "boller-i-karry"}).json() == []


def test_added_original_images_are_on_disk_and_in_the_frontmatter(
    client: TestClient, write_file: WriteFile, library_dir: Path
) -> None:
    write_file("boller-i-karry.md", BOLLER)
    write_file("boller-i-karry.1.jpg", jpeg())
    files = [("billeder", ("a.jpg", jpeg(color="red"), "image/jpeg")), ("billeder", ("b.jpg", jpeg(color="blue"), "image/jpeg"))]

    response = client.post("api/opskrifter/boller-i-karry/originalbilleder", files=files)

    assert response.status_code == 200
    assert response.json()["originalbilleder"] == [
        "api/billeder/boller-i-karry.1.jpg",
        "api/billeder/boller-i-karry.2.jpg",
        "api/billeder/boller-i-karry.3.jpg",
    ]
    assert (library_dir / "boller-i-karry.3.jpg").is_file()
    text = (library_dir / "boller-i-karry.md").read_text(encoding="utf-8")
    assert "originalbilleder: [boller-i-karry.1.jpg, boller-i-karry.2.jpg, boller-i-karry.3.jpg]\n" in text
    assert text.replace("[boller-i-karry.1.jpg, boller-i-karry.2.jpg, boller-i-karry.3.jpg]", "[boller-i-karry.1.jpg]") == BOLLER


def test_added_original_images_do_not_overwrite_existing_files(
    client: TestClient, write_file: WriteFile, library_dir: Path
) -> None:
    write_file("kage.md", "---\ntitel: Kage\n---\n")
    write_file("kage.1.jpg", b"et billede, der ikke er i frontmatter")

    client.post("api/opskrifter/kage/originalbilleder", files=[("billeder", ("a.jpg", jpeg(), "image/jpeg"))])

    assert (library_dir / "kage.1.jpg").read_bytes() == b"et billede, der ikke er i frontmatter"
    assert client.get("api/opskrifter/kage").json()["originalbilleder"] == ["api/billeder/kage.2.jpg"]


def test_a_file_that_cannot_be_read_cannot_be_edited(client: TestClient, write_file: WriteFile, library_dir: Path) -> None:
    broken = "---\ntitel: [Pasta\n---\n"
    path = write_file("pasta.md", broken)

    assert update(client, "pasta", {"titel": "Pasta"}).status_code == 409
    images = [("billeder", ("a.jpg", jpeg(), "image/jpeg"))]
    assert client.post("api/opskrifter/pasta/originalbilleder", files=images).status_code == 409
    assert path.read_text(encoding="utf-8") == broken
    assert sorted(p.name for p in library_dir.iterdir()) == ["pasta.md"]


def test_editing_an_unknown_recipe_gives_404(client: TestClient) -> None:
    assert update(client, "findes-ikke", {"titel": "X"}).status_code == 404
