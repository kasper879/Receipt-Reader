from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient

WriteFile = Callable[[str, str | bytes], Path]

BOLLER_I_KARRY = """
    ---
    titel: Boller i karry
    portioner: 4
    forberedelse: 30
    total: 75
    vurdering: 5
    tags: [aftensmad, klassiker]
    kilde: Mormors kogebog
    oprettet: 2026-10-21
    retbillede: boller-i-karry.ret.jpg
    originalbilleder: [boller-i-karry.1.jpg, boller-i-karry.2.jpg]
    ---

    ## Ingredienser

    ### Til kødbollerne
    - 500 g hakket svinekød
    - 1 løg, finthakket

    ### Til sovsen
    - 2 spsk karry
    - salt og peber

    ## Fremgangsmåde

    1. Bland kødet med løg.
    2. Form bollerne.

    ## Noter

    Mormor kom altid et revet æble i sovsen.
    """


def test_empty_library_lists_nothing(client: TestClient) -> None:
    response = client.get("api/opskrifter")

    assert response.status_code == 200
    assert response.json() == []


def test_library_lists_recipe_from_file(client: TestClient, write_file: WriteFile) -> None:
    write_file("boller-i-karry.md", BOLLER_I_KARRY)

    response = client.get("api/opskrifter")

    assert response.json() == [
        {
            "id": "boller-i-karry",
            "titel": "Boller i karry",
            "kilde": "Mormors kogebog",
            "total": 75,
            "tags": ["aftensmad", "klassiker"],
            "vurdering": 5,
            "billede": "api/billeder/boller-i-karry.ret.jpg",
            "oprettet": "2026-10-21",
            "advarsel": None,
        }
    ]


def test_empty_fields_are_not_given(client: TestClient, write_file: WriteFile) -> None:
    write_file(
        "mormors-aeblekage.md",
        """
        ---
        titel: Mormors æblekage
        portioner:
        total:
        tags: []
        ---

        ## Ingredienser

        - 6 æbler
        """,
    )

    [item] = client.get("api/opskrifter").json()

    assert item == {
        "id": "mormors-aeblekage",
        "titel": "Mormors æblekage",
        "kilde": None,
        "total": None,
        "tags": [],
        "vurdering": None,
        "billede": None,
        "oprettet": None,
        "advarsel": None,
    }


def test_library_is_sorted_newest_first(client: TestClient, write_file: WriteFile) -> None:
    write_file("a.md", "---\ntitel: Gammel\noprettet: 2025-01-05\n---\n")
    write_file("b.md", "---\ntitel: Uden dato\n---\n")
    write_file("c.md", "---\ntitel: Ny\noprettet: 2026-10-21\n---\n")
    write_file("d.md", "---\ntitel: Midt\noprettet: 2026-03-01\n---\n")

    titles = [item["titel"] for item in client.get("api/opskrifter").json()]

    assert titles == ["Ny", "Midt", "Gammel", "Uden dato"]


def test_image_falls_back_to_first_original_image(client: TestClient, write_file: WriteFile) -> None:
    write_file("kage.md", "---\ntitel: Kage\noriginalbilleder: [kage.1.jpg, kage.2.jpg]\n---\n")

    [item] = client.get("api/opskrifter").json()

    assert item["billede"] == "api/billeder/kage.1.jpg"


def test_images_are_served_via_the_api(client: TestClient, write_file: WriteFile) -> None:
    write_file("boller-i-karry.md", BOLLER_I_KARRY)
    write_file("boller-i-karry.ret.jpg", b"\xff\xd8jpeg-bytes")

    [item] = client.get("api/opskrifter").json()
    response = client.get(item["billede"])

    assert response.status_code == 200
    assert response.content == b"\xff\xd8jpeg-bytes"
    assert response.headers["content-type"] == "image/jpeg"


def test_only_images_in_the_library_folder_are_served(
    client: TestClient, write_file: WriteFile, library_dir: Path
) -> None:
    write_file("boller-i-karry.md", BOLLER_I_KARRY)
    (library_dir.parent / "hemmelig.jpg").write_bytes(b"x")

    assert client.get("api/billeder/mangler.jpg").status_code == 404
    assert client.get("api/billeder/boller-i-karry.md").status_code == 404
    assert client.get("api/billeder/..%2Fhemmelig.jpg").status_code == 404


def test_only_markdown_files_outside_hidden_folders_are_recipes(
    client: TestClient, write_file: WriteFile, library_dir: Path
) -> None:
    write_file("kage.md", "---\ntitel: Kage\n---\n")
    write_file("noter.txt", "ikke en opskrift")
    (library_dir / ".papirkurv").mkdir()
    write_file(".papirkurv/slettet.md", "---\ntitel: Slettet\n---\n")

    titles = [item["titel"] for item in client.get("api/opskrifter").json()]

    assert titles == ["Kage"]


def test_a_file_that_cannot_be_read_is_listed_with_a_warning(client: TestClient, write_file: WriteFile) -> None:
    write_file("kage.md", "---\ntitel: Kage\noprettet: 2026-01-01\n---\n")
    write_file("pasta-med-pesto.md", "---\ntitel: [Pasta\n---\n")

    response = client.get("api/opskrifter")

    assert response.status_code == 200
    broken = next(item for item in response.json() if item["id"] == "pasta-med-pesto")
    assert broken["titel"] == "pasta-med-pesto"
    assert broken["advarsel"]


def test_a_file_that_is_not_utf8_is_listed_with_a_warning(client: TestClient, write_file: WriteFile) -> None:
    write_file("roedkaal.md", "---\ntitel: Rødkål\n---\n".encode("cp1252"))

    [item] = client.get("api/opskrifter").json()

    assert item["id"] == "roedkaal"
    assert item["advarsel"]


def test_image_names_are_url_encoded(client: TestClient, write_file: WriteFile) -> None:
    write_file("kage.md", "---\ntitel: Kage\nretbillede: 'kage #1.jpg'\n---\n")
    write_file("kage #1.jpg", b"jpeg")

    [item] = client.get("api/opskrifter").json()

    assert item["billede"] == "api/billeder/kage%20%231.jpg"
    assert client.get(item["billede"]).content == b"jpeg"
