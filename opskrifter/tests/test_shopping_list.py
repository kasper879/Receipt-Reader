"""Indkøbslisten i Home Assistant: klienten mod en mocket HTTP-klient, og API'et med en falsk liste."""

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient

from recipe_reader.app import create_app
from recipe_reader.settings import Settings
from recipe_reader.shopping_list import HomeAssistantShoppingList, NoShoppingList, ShoppingListError, shopping_list_from_settings

WriteFile = Callable[[str, str | bytes], Path]
TOKEN = "supervisor-hemmelig-token"
BASE = "http://supervisor/core/api"


def ha(handler: Callable[[httpx2.Request], httpx2.Response]) -> HomeAssistantShoppingList:
    return HomeAssistantShoppingList(BASE, TOKEN, "todo.indkobsliste", client=httpx2.Client(transport=httpx2.MockTransport(handler)))


def home_assistant(
    requests: list[httpx2.Request], *, list_exists: bool = True, supported_features: int = 127, add_status: int = 200
) -> Callable[[httpx2.Request], httpx2.Response]:
    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        if request.method == "GET":
            state = {"entity_id": "todo.indkobsliste", "state": "3", "attributes": {"supported_features": supported_features}}
            return httpx2.Response(200, json=state) if list_exists else httpx2.Response(404, json={"message": "Entity not found."})
        return httpx2.Response(add_status, json=[] if add_status == 200 else {"message": "Entity does not support setting field 'description'"})

    return handler


def test_each_ingredient_becomes_an_item_with_the_recipe_as_description() -> None:
    requests: list[httpx2.Request] = []

    ha(home_assistant(requests)).add(["600 g hakket svinekød", "2 spsk karry"], "Til Boller i karry")

    [check, *calls] = requests
    assert (check.method, str(check.url)) == ("GET", f"{BASE}/states/todo.indkobsliste")
    assert [str(call.url) for call in calls] == [f"{BASE}/services/todo/add_item"] * 2
    assert [json.loads(call.content) for call in calls] == [
        {"entity_id": "todo.indkobsliste", "item": "600 g hakket svinekød", "description": "Til Boller i karry"},
        {"entity_id": "todo.indkobsliste", "item": "2 spsk karry", "description": "Til Boller i karry"},
    ]
    assert all(request.headers["authorization"] == f"Bearer {TOKEN}" for request in requests)


def test_a_list_that_cannot_store_descriptions_gets_the_items_without() -> None:
    requests: list[httpx2.Request] = []

    # Den indbyggede Indkøbsliste: opret, slet, opdatér og flyt, men ingen beskrivelse.
    ha(home_assistant(requests, supported_features=15)).add(["2 spsk karry"], "Til Boller i karry")

    assert json.loads(requests[1].content) == {"entity_id": "todo.indkobsliste", "item": "2 spsk karry"}


def test_an_item_home_assistant_rejects_is_not_reported_as_a_missing_list(caplog: pytest.LogCaptureFixture) -> None:
    requests: list[httpx2.Request] = []

    with pytest.raises(ShoppingListError) as raised:
        ha(home_assistant(requests, add_status=400)).add(["2 spsk karry"], None)

    assert "findes ikke" not in str(raised.value)
    assert "400" in str(raised.value)
    assert "does not support" in caplog.text


def test_a_list_that_does_not_exist_gives_a_clear_message_and_adds_nothing() -> None:
    requests: list[httpx2.Request] = []

    with pytest.raises(ShoppingListError) as raised:
        ha(home_assistant(requests, list_exists=False)).add(["2 spsk karry"], None)

    assert "todo.indkobsliste" in str(raised.value)
    assert "indkoebsliste" in str(raised.value)
    assert [request.method for request in requests] == ["GET"]


@pytest.mark.parametrize("status", [401, 403])
def test_no_access_to_home_assistant_gives_a_clear_message(status: int) -> None:
    with pytest.raises(ShoppingListError) as raised:
        ha(lambda request: httpx2.Response(status, json={"message": "Unauthorized"})).add(["karry"], None)

    assert "adgang" in str(raised.value)


def test_home_assistant_not_answering_gives_a_clear_message(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("ingen forbindelse")

    with pytest.raises(ShoppingListError) as raised:
        ha(handler).add(["karry"], None)

    assert "Home Assistant" in str(raised.value)
    assert TOKEN not in caplog.text and TOKEN not in str(raised.value)


def test_without_a_token_there_is_no_shopping_list(tmp_path: Path) -> None:
    settings = Settings(library_dir=tmp_path, index_path=tmp_path / "index.sqlite")

    shopping_list = shopping_list_from_settings(settings)

    assert isinstance(shopping_list, NoShoppingList)
    assert not shopping_list.available


def test_with_a_token_the_list_comes_from_the_settings(tmp_path: Path) -> None:
    settings = Settings(library_dir=tmp_path, index_path=tmp_path / "index.sqlite", ha_token=TOKEN, shopping_list="todo.indkobsliste")

    shopping_list = shopping_list_from_settings(settings)

    assert isinstance(shopping_list, HomeAssistantShoppingList)
    assert shopping_list.entity_id == "todo.indkobsliste"
    assert TOKEN not in repr(shopping_list) and TOKEN not in repr(settings)


# ---------------- API'et ----------------


class FakeShoppingList:
    def __init__(self, available: bool = True) -> None:
        self.available = available
        self.entity_id = "todo.shopping_list"
        self.added: list[tuple[list[str], str | None]] = []
        self.error: ShoppingListError | None = None

    def add(self, items: list[str], description: str | None) -> None:
        if self.error:
            raise self.error
        self.added.append((items, description))


@pytest.fixture
def shopping() -> FakeShoppingList:
    return FakeShoppingList()


@pytest.fixture
def shop_client(settings: Settings, shopping: FakeShoppingList) -> Any:
    with TestClient(create_app(settings, shopping_list=shopping)) as client:
        yield client


def test_the_frontend_can_see_whether_there_is_a_shopping_list(shop_client: TestClient, shopping: FakeShoppingList) -> None:
    assert shop_client.get("api/indkoebsliste").json() == {"tilgaengelig": True, "liste": "todo.shopping_list"}
    shopping.available = False
    assert shop_client.get("api/indkoebsliste").json()["tilgaengelig"] is False


def test_ingredients_are_put_on_the_shopping_list(shop_client: TestClient, shopping: FakeShoppingList, write_file: WriteFile) -> None:
    write_file("boller-i-karry.md", "---\ntitel: Boller i karry\n---\n")

    response = shop_client.post("api/opskrifter/boller-i-karry/indkoebsliste", json={"varer": [" 600 g hakket svinekød ", "", "2 spsk karry"]})

    assert response.status_code == 200
    assert response.json() == {"antal": 2}
    assert shopping.added == [(["600 g hakket svinekød", "2 spsk karry"], "Til Boller i karry")]


def test_an_error_from_home_assistant_is_shown(shop_client: TestClient, shopping: FakeShoppingList, write_file: WriteFile) -> None:
    write_file("kage.md", "---\ntitel: Kage\n---\n")
    shopping.error = ShoppingListError("Indkøbslisten todo.x findes ikke.")

    response = shop_client.post("api/opskrifter/kage/indkoebsliste", json={"varer": ["3 æg"]})

    assert response.status_code == 409
    assert response.json()["detail"] == "Indkøbslisten todo.x findes ikke."


def test_nothing_to_add_or_no_shopping_list_is_rejected(shop_client: TestClient, shopping: FakeShoppingList, write_file: WriteFile) -> None:
    write_file("kage.md", "---\ntitel: Kage\n---\n")

    assert shop_client.post("api/opskrifter/kage/indkoebsliste", json={"varer": [" "]}).status_code == 422
    assert shop_client.post("api/opskrifter/findes-ikke/indkoebsliste", json={"varer": ["æg"]}).status_code == 404
    shopping.available = False
    assert shop_client.post("api/opskrifter/kage/indkoebsliste", json={"varer": ["æg"]}).status_code == 409
    assert shopping.added == []
