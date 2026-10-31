"""Indkøbskurven: sammenlægning af ingredienser fra flere opskrifter, og API'et med en falsk indkøbsliste."""

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from recipe_reader.app import create_app
from recipe_reader.basket import BasketRecipe, combine
from recipe_reader.recipe_format import Ingredient
from recipe_reader.settings import Settings
from recipe_reader.shopping_list import ShoppingItem, ShoppingListError

WriteFile = Callable[[str, str | bytes], Path]


def recipe(titel: str, *varer: Ingredient) -> BasketRecipe:
    return BasketRecipe(titel.lower(), titel, None, list(varer))


def test_the_same_ingredient_in_the_same_unit_is_added_together() -> None:
    lines = combine(
        [
            recipe("Boller i karry", Ingredient(2, "spsk", "karry"), Ingredient(600, "g", "hakket svinekød")),
            recipe("Dahl", Ingredient(1, "spsk", "Karry ")),
        ]
    )

    assert [(line.tekst, line.opskrifter) for line in lines] == [
        ("3 spsk karry", ["Boller i karry", "Dahl"]),
        ("600 g hakket svinekød", ["Boller i karry"]),
    ]


def test_different_units_stay_on_separate_lines() -> None:
    lines = combine([recipe("Suppe", Ingredient(200, "g", "gulerod")), recipe("Salat", Ingredient(2, "stk", "gulerod"))])

    assert [line.tekst for line in lines] == ["200 g gulerod", "2 stk gulerod"]


def test_an_ingredient_without_amount_appears_once() -> None:
    lines = combine(
        [
            recipe("Suppe", Ingredient(None, None, "peber"), Ingredient(1, "tsk", "peber")),
            recipe("Salat", Ingredient(None, None, "Peber")),
        ]
    )

    assert [(line.tekst, line.opskrifter) for line in lines] == [("peber", ["Suppe", "Salat"]), ("1 tsk peber", ["Suppe"])]


def test_fractions_and_converted_portions_are_added_and_formatted() -> None:
    # ½ tsk til 4 portioner omregnet til 6 portioner er ¾ tsk.
    lines = combine([recipe("Suppe", Ingredient(0.75, "tsk", "salt")), recipe("Salat", Ingredient(0.25, "tsk", "salt"))])

    assert [line.tekst for line in lines] == ["1 tsk salt"]
    assert combine([recipe("Suppe", Ingredient(2 / 3, "dl", "fløde"))])[0].tekst == "⅔ dl fløde"


# ---------------- API'et ----------------


class FakeShoppingList:
    def __init__(self, available: bool = True) -> None:
        self.available = available
        self.entity_id = "todo.shopping_list"
        self.added: list[ShoppingItem] = []
        self.error: ShoppingListError | None = None

    def add(self, items: list[ShoppingItem]) -> None:
        if self.error:
            raise self.error
        self.added.extend(items)


@pytest.fixture
def shopping() -> FakeShoppingList:
    return FakeShoppingList()


@pytest.fixture
def start(settings: Settings, shopping: FakeShoppingList) -> Callable[[], AbstractContextManager[TestClient]]:
    return lambda: TestClient(create_app(settings, shopping_list=shopping))


@pytest.fixture
def shop_client(start: Callable[[], AbstractContextManager[TestClient]], write_file: WriteFile) -> Iterator[TestClient]:
    write_file("boller-i-karry.md", "---\ntitel: Boller i karry\nportioner: 4\n---\n")
    write_file("dahl.md", "---\ntitel: Dahl\n---\n")
    with start() as client:
        yield client


def put(client: TestClient, recipe_id: str, *varer: dict[str, Any], portioner: int | None = None) -> Any:
    return client.put(f"api/indkoebskurv/opskrifter/{recipe_id}", json={"portioner": portioner, "varer": list(varer)})


KARRY = {"maengde": 2, "enhed": "spsk", "navn": "karry"}
SVINEKOED = {"maengde": 600, "enhed": "g", "navn": "hakket svinekød"}
PEBER = {"maengde": None, "enhed": None, "navn": "peber"}


def test_the_frontend_can_see_whether_there_is_a_shopping_list(shop_client: TestClient, shopping: FakeShoppingList) -> None:
    assert shop_client.get("api/indkoebsliste").json() == {"tilgaengelig": True, "liste": "todo.shopping_list"}
    shopping.available = False
    assert shop_client.get("api/indkoebsliste").json()["tilgaengelig"] is False


def test_recipes_in_the_basket_are_added_together(shop_client: TestClient) -> None:
    put(shop_client, "boller-i-karry", KARRY, SVINEKOED, portioner=4)
    basket = put(shop_client, "dahl", {**KARRY, "maengde": 1}, PEBER).json()

    assert basket["opskrifter"] == [
        {"id": "boller-i-karry", "titel": "Boller i karry", "portioner": 4, "antal": 2},
        {"id": "dahl", "titel": "Dahl", "portioner": None, "antal": 2},
    ]
    assert [(line["tekst"], line["opskrifter"], line["har_maengde"]) for line in basket["linjer"]] == [
        ("3 spsk karry", ["Boller i karry", "Dahl"], True),
        ("600 g hakket svinekød", ["Boller i karry"], True),
        ("peber", ["Dahl"], False),
    ]


def test_putting_a_recipe_again_replaces_its_items(shop_client: TestClient) -> None:
    put(shop_client, "boller-i-karry", KARRY, SVINEKOED, portioner=4)
    basket = put(shop_client, "boller-i-karry", {**KARRY, "maengde": 3}, portioner=6).json()

    assert [recipe["portioner"] for recipe in basket["opskrifter"]] == [6]
    assert [line["tekst"] for line in basket["linjer"]] == ["3 spsk karry"]


def test_a_recipe_can_be_removed_again_and_its_amounts_are_subtracted(shop_client: TestClient) -> None:
    put(shop_client, "boller-i-karry", KARRY)
    put(shop_client, "dahl", {**KARRY, "maengde": 1})

    basket = shop_client.delete("api/indkoebskurv/opskrifter/dahl").json()

    assert [line["tekst"] for line in basket["linjer"]] == ["2 spsk karry"]
    assert shop_client.delete("api/indkoebskurv").json() == {"opskrifter": [], "linjer": []}


def test_the_basket_survives_a_restart(start: Callable[[], AbstractContextManager[TestClient]], shop_client: TestClient) -> None:
    put(shop_client, "boller-i-karry", KARRY, PEBER)

    with start() as restarted:
        assert [line["tekst"] for line in restarted.get("api/indkoebskurv").json()["linjer"]] == ["2 spsk karry", "peber"]


def test_a_basket_file_that_cannot_be_read_starts_empty(shop_client: TestClient, write_file: WriteFile) -> None:
    write_file(".indkoebskurv.json", "{ikke json")

    assert shop_client.get("api/indkoebskurv").json() == {"opskrifter": [], "linjer": []}


def test_nothing_or_an_unknown_recipe_cannot_be_put_in_the_basket(shop_client: TestClient) -> None:
    assert put(shop_client, "boller-i-karry", {**KARRY, "navn": " "}).status_code == 422
    assert put(shop_client, "findes-ikke", KARRY).status_code == 404


def test_the_chosen_items_are_sent_with_the_recipes_as_description_and_the_basket_is_emptied(
    shop_client: TestClient, shopping: FakeShoppingList
) -> None:
    put(shop_client, "boller-i-karry", KARRY, SVINEKOED)
    lines = put(shop_client, "dahl", {**KARRY, "maengde": 1}, PEBER).json()["linjer"]
    chosen = [line["noegle"] for line in lines if line["tekst"] != "peber"]

    response = shop_client.post("api/indkoebskurv/send", json={"noegler": chosen})

    assert response.json() == {"antal": 2}
    assert shopping.added == [
        ShoppingItem("3 spsk karry", "Til Boller i karry, Dahl"),
        ShoppingItem("600 g hakket svinekød", "Til Boller i karry"),
    ]
    assert shop_client.get("api/indkoebskurv").json() == {"opskrifter": [], "linjer": []}


def test_when_sending_fails_the_basket_stays(shop_client: TestClient, shopping: FakeShoppingList) -> None:
    lines = put(shop_client, "boller-i-karry", KARRY).json()["linjer"]
    shopping.error = ShoppingListError("Indkøbslisten todo.x findes ikke.")

    response = shop_client.post("api/indkoebskurv/send", json={"noegler": [lines[0]["noegle"]]})

    assert response.status_code == 409
    assert response.json()["detail"] == "Indkøbslisten todo.x findes ikke."
    assert shop_client.get("api/indkoebskurv").json()["linjer"] == lines


def test_nothing_chosen_or_no_shopping_list_is_rejected(shop_client: TestClient, shopping: FakeShoppingList) -> None:
    lines = put(shop_client, "boller-i-karry", KARRY).json()["linjer"]

    assert shop_client.post("api/indkoebskurv/send", json={"noegler": []}).status_code == 422
    shopping.available = False
    assert shop_client.post("api/indkoebskurv/send", json={"noegler": [lines[0]["noegle"]]}).status_code == 409
    assert shopping.added == []
    assert len(shop_client.get("api/indkoebskurv").json()["linjer"]) == 1
