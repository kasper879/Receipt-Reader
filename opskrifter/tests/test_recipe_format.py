"""Opskriftsformatet, set gennem API'et for en enkelt opskrift."""

from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient

from tests.test_library import BOLLER_I_KARRY

WriteFile = Callable[[str, str | bytes], Path]


def ingredients_of(client: TestClient, write_file: WriteFile, lines: str) -> list[dict[str, object]]:
    write_file("test.md", f"---\ntitel: Test\n---\n\n## Ingredienser\n\n{lines}\n")
    [group] = client.get("api/opskrifter/test").json()["ingredienser"]
    return group["linjer"]  # type: ignore[no-any-return]


def test_recipe_is_read_with_all_sections(client: TestClient, write_file: WriteFile) -> None:
    write_file("boller-i-karry.md", BOLLER_I_KARRY)

    response = client.get("api/opskrifter/boller-i-karry")

    assert response.status_code == 200
    assert response.json() == {
        "id": "boller-i-karry",
        "titel": "Boller i karry",
        "portioner": 4,
        "forberedelse": 30,
        "total": 75,
        "vurdering": 5,
        "tags": ["aftensmad", "klassiker"],
        "kilde": "Mormors kogebog",
        "oprettet": "2026-10-21",
        "retbillede": "api/billeder/boller-i-karry.ret.jpg",
        "originalbilleder": ["api/billeder/boller-i-karry.1.jpg", "api/billeder/boller-i-karry.2.jpg"],
        "ingredienser": [
            {
                "gruppe": "Til kødbollerne",
                "linjer": [
                    {"maengde": 500, "enhed": "g", "navn": "hakket svinekød"},
                    {"maengde": 1, "enhed": None, "navn": "løg, finthakket"},
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
        "advarsel": None,
        "raa": None,
    }


def test_ingredients_before_the_first_group_have_no_group(client: TestClient, write_file: WriteFile) -> None:
    write_file(
        "pandekager.md",
        """
        ---
        titel: Pandekager
        ---

        ## Ingredienser

        - 3 æg
        - 5 dl mælk

        ### Til servering
        - sukker
        """,
    )

    groups = client.get("api/opskrifter/pandekager").json()["ingredienser"]

    assert groups == [
        {
            "gruppe": None,
            "linjer": [
                {"maengde": 3, "enhed": None, "navn": "æg"},
                {"maengde": 5, "enhed": "dl", "navn": "mælk"},
            ],
        },
        {"gruppe": "Til servering", "linjer": [{"maengde": None, "enhed": None, "navn": "sukker"}]},
    ]


def test_quantities_can_be_decimals_fractions_and_unicode_fractions(
    client: TestClient, write_file: WriteFile
) -> None:
    lines = ingredients_of(
        client,
        write_file,
        "- 1,5 dl fløde\n- 2.5 kg kartofler\n- 1/2 tsk salt\n- ½ citron\n- 1½ l vand\n- 1 1/2 spsk honning\n- ¾ dl sukker",
    )

    assert [(line["maengde"], line["enhed"], line["navn"]) for line in lines] == [
        (1.5, "dl", "fløde"),
        (2.5, "kg", "kartofler"),
        (0.5, "tsk", "salt"),
        (0.5, None, "citron"),
        (1.5, "l", "vand"),
        (1.5, "spsk", "honning"),
        (0.75, "dl", "sukker"),
    ]


def test_unit_only_counts_when_it_is_on_the_fixed_list(client: TestClient, write_file: WriteFile) -> None:
    lines = ingredients_of(client, write_file, "- 2 fed hvidløg\n- 1 dåse tomater\n- 2 store løg\n- 1 g\n- gær")

    assert [(line["maengde"], line["enhed"], line["navn"]) for line in lines] == [
        (2, "fed", "hvidløg"),
        (1, "dåse", "tomater"),
        (2, None, "store løg"),
        (1, None, "g"),
        (None, None, "gær"),
    ]


def test_missing_sections_are_empty(client: TestClient, write_file: WriteFile) -> None:
    write_file("tom.md", "---\ntitel: Tom\n---\n")

    recipe = client.get("api/opskrifter/tom").json()

    assert (recipe["ingredienser"], recipe["trin"], recipe["noter"]) == ([], [], None)


def test_a_step_can_span_several_lines(client: TestClient, write_file: WriteFile) -> None:
    write_file("trin.md", "---\ntitel: Trin\n---\n\n## Fremgangsmåde\n\n1. Rør dejen\n   godt sammen.\n2. Bag den.\n")

    assert client.get("api/opskrifter/trin").json()["trin"] == ["Rør dejen godt sammen.", "Bag den."]


def test_unknown_recipe_gives_404(client: TestClient) -> None:
    assert client.get("api/opskrifter/findes-ikke").status_code == 404


def test_an_impossible_fraction_is_part_of_the_name(client: TestClient, write_file: WriteFile) -> None:
    lines = ingredients_of(client, write_file, "- 1/0 tsk salt")

    assert [(line["maengde"], line["enhed"], line["navn"]) for line in lines] == [(None, None, "1/0 tsk salt")]


def test_steps_can_be_written_as_bullets(client: TestClient, write_file: WriteFile) -> None:
    write_file("trin.md", "---\ntitel: Trin\n---\n\n## Fremgangsmåde\n\n- Rør dejen.\n- Bag den.\n")

    assert client.get("api/opskrifter/trin").json()["trin"] == ["Rør dejen.", "Bag den."]


def test_a_unicode_fraction_can_follow_a_space(client: TestClient, write_file: WriteFile) -> None:
    lines = ingredients_of(client, write_file, "- 1 ½ dl mælk")

    assert [(line["maengde"], line["enhed"], line["navn"]) for line in lines] == [(1.5, "dl", "mælk")]


def test_a_rating_outside_one_to_five_gives_a_warning(client: TestClient, write_file: WriteFile) -> None:
    write_file("kage.md", "---\ntitel: Kage\nvurdering: 7\n---\n")

    assert client.get("api/opskrifter/kage").json()["advarsel"]
