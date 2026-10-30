"""Importér en opskrift fra et link, med en falsk henter og den falske aflæser."""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from recipe_reader.reader import RejectedError, TechnicalError
from recipe_reader.web_page import PageContent
from tests.conftest import FakeFetcher, FakeReader
from tests.images import jpeg, size_of
from tests.test_new_recipe import BOLLER, retry_now, save, wait_for

LINK = "https://madensverden.test/boller-i-karry/"
PHOTO = "https://madensverden.test/billeder/boller.jpg"


@pytest.fixture
def page(fake_fetcher: FakeFetcher) -> PageContent:
    content = PageContent(
        url=LINK,
        title="Boller i karry - Madens Verden",
        recipes=[{"@type": "Recipe", "name": "Boller i karry", "recipeIngredient": ["2 tsk karry"]}],
        image_url=PHOTO,
        text="Boller i karry er en klassisk dansk hverdagsret.",
    )
    fake_fetcher.pages[LINK] = content
    fake_fetcher.images[PHOTO] = jpeg(2400, 1600, color="orange")
    return content


def import_link(client: TestClient, link: str = LINK) -> Any:
    response = client.post("api/aflaesninger/link", json={"link": link})
    assert response.status_code == 202, response.text
    return wait_for(client, response.json()["id"])


@pytest.mark.usefixtures("page")
def test_a_link_gives_a_draft_from_the_page(client: TestClient, fake_reader: FakeReader) -> None:
    fake_reader.udkast = [BOLLER]

    reading = import_link(client)

    assert reading["status"] == "udkast"
    assert reading["link"] == LINK
    assert reading["originalbilleder"] == []
    assert [draft["titel"] for draft in reading["udkast"]] == ["Boller i karry"]
    [sent] = fake_reader.pages
    assert sent.recipes[0]["name"] == "Boller i karry"
    assert "klassisk dansk hverdagsret" in sent.text
    assert fake_reader.calls == []


@pytest.mark.usefixtures("page")
def test_the_photo_of_the_dish_on_the_page_is_shown_in_the_review(client: TestClient, fake_reader: FakeReader) -> None:
    fake_reader.udkast = [BOLLER]

    reading = import_link(client)

    assert reading["retbillede"] == f"api/aflaesninger/{reading['id']}/billeder/ret.jpg"
    assert size_of(client.get(reading["retbillede"]).content) == (1600, 1067)


@pytest.mark.usefixtures("page")
def test_saving_writes_the_link_and_the_dish_photo(client: TestClient, fake_reader: FakeReader, library_dir: Path) -> None:
    fake_reader.udkast = [BOLLER]
    reading = import_link(client)

    recipe_id = save(client, reading["id"], 1, BOLLER).json()["id"]

    text = (library_dir / f"{recipe_id}.md").read_text(encoding="utf-8")
    assert f"link: {LINK}\n" in text
    assert f"retbillede: {recipe_id}.ret.jpg\n" in text
    assert "originalbilleder" not in text
    assert (library_dir / f"{recipe_id}.ret.jpg").is_file()
    recipe = client.get(f"api/opskrifter/{recipe_id}").json()
    assert recipe["link"] == LINK
    assert recipe["retbillede"] == f"api/billeder/{recipe_id}.ret.jpg"


@pytest.mark.usefixtures("page")
def test_the_link_is_kept_when_the_recipe_is_edited(client: TestClient, fake_reader: FakeReader) -> None:
    fake_reader.udkast = [BOLLER]
    recipe_id = save(client, import_link(client)["id"], 1, BOLLER).json()["id"]
    recipe = client.get(f"api/opskrifter/{recipe_id}").json()
    draft = {key: recipe[key] for key in ["titel", "portioner", "forberedelse", "total", "tags", "kilde", "ingredienser", "trin", "noter"]}

    client.put(f"api/opskrifter/{recipe_id}", json={"udkast": {**draft, "titel": "Mormors boller i karry"}})

    assert client.get(f"api/opskrifter/{recipe_id}").json()["link"] == LINK


def test_a_page_without_a_photo_gives_a_recipe_without_a_dish_photo(
    client: TestClient, fake_reader: FakeReader, fake_fetcher: FakeFetcher, library_dir: Path
) -> None:
    fake_fetcher.pages[LINK] = PageContent(url=LINK, title="Boller", text="Tekst")
    fake_reader.udkast = [BOLLER]

    recipe_id = save(client, import_link(client)["id"], 1, BOLLER).json()["id"]

    assert not (library_dir / f"{recipe_id}.ret.jpg").exists()


@pytest.mark.usefixtures("page")
def test_a_photo_that_cannot_be_fetched_does_not_stop_the_import(
    client: TestClient, fake_reader: FakeReader, fake_fetcher: FakeFetcher
) -> None:
    fake_fetcher.images.clear()
    fake_reader.udkast = [BOLLER]

    reading = import_link(client)

    assert reading["status"] == "udkast"
    assert reading["retbillede"] is None


@pytest.mark.parametrize("link", ["ftp://madensverden.test/", "madensverden.dk/boller", ""])
def test_a_link_that_is_not_http_is_rejected(client: TestClient, link: str) -> None:
    assert client.post("api/aflaesninger/link", json={"link": link}).status_code == 422
    assert client.get("api/aflaesninger").json() == []


@pytest.mark.usefixtures("page")
def test_a_page_that_cannot_be_fetched_now_gives_a_pending_reading_that_can_be_retried(
    client: TestClient, fake_reader: FakeReader, fake_fetcher: FakeFetcher
) -> None:
    fake_fetcher.error = TechnicalError("Siden kunne ikke hentes lige nu.")

    reading = import_link(client)

    assert (reading["status"], reading["automatisk"], reading["fejl"]) == ("ventende", True, "Siden kunne ikke hentes lige nu.")
    fake_fetcher.error = None
    fake_reader.udkast = [BOLLER]
    assert retry_now(client, reading["id"]).json()["status"] == "udkast"


def test_a_page_that_does_not_exist_waits_for_the_user(client: TestClient, fake_fetcher: FakeFetcher) -> None:
    fake_fetcher.error = RejectedError("Siden kunne ikke hentes (fejl 404). Tjek linket.")

    reading = import_link(client)

    assert (reading["status"], reading["automatisk"]) == ("ventende", False)


@pytest.mark.usefixtures("page")
def test_a_reading_from_a_link_survives_a_restart(client: TestClient, fake_fetcher: FakeFetcher, restart: Any) -> None:
    fake_fetcher.error = TechnicalError("Ingen forbindelse")
    reading = import_link(client)

    with restart() as restarted:
        [listed] = restarted.get("api/aflaesninger").json()
        assert (listed["id"], listed["link"]) == (reading["id"], LINK)
