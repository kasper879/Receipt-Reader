"""Automatisk retbillede: et foto af retten på originalbillederne beskæres og gemmes som retbillede."""

import io
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from PIL import Image

from tests.conftest import FakeReader
from tests.images import jpeg, size_of
from tests.test_new_recipe import BOLLER, save, start_reading

LEFT_HALF = {"billede": 1, "venstre": 0.0, "top": 0.0, "hoejre": 0.5, "bund": 1.0}


def red_and_blue(width: int = 400, height: int = 300) -> bytes:
    """Et billede, der er rødt i venstre halvdel og blåt i højre."""
    image = Image.new("RGB", (width, height), "blue")
    image.paste(Image.new("RGB", (width // 2, height), "red"), (0, 0))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=95)
    return out.getvalue()


def color_at_centre(data: bytes) -> tuple[int, int, int]:
    with Image.open(io.BytesIO(data)) as image:
        rgb = image.convert("RGB")
        return rgb.getpixel((rgb.width // 2, rgb.height // 2))  # type: ignore[return-value]


def read_with_area(client: TestClient, fake_reader: FakeReader, area: dict[str, Any] | None, *images: bytes) -> Any:
    fake_reader.udkast = [{**BOLLER, "retbillede_omraade": area}]
    return start_reading(client, *(images or (red_and_blue(),))).json()


def test_the_photo_of_the_dish_becomes_the_dish_photo(
    client: TestClient, fake_reader: FakeReader, library_dir: Path
) -> None:
    reading = read_with_area(client, fake_reader, LEFT_HALF)

    recipe_id = save(client, reading["id"], 1, BOLLER).json()["id"]

    photo = library_dir / f"{recipe_id}.ret.jpg"
    assert size_of(photo.read_bytes()) == (200, 300)
    red, green, blue = color_at_centre(photo.read_bytes())
    assert red > 200 and green < 60 and blue < 60
    assert f"retbillede: {recipe_id}.ret.jpg\n" in (library_dir / f"{recipe_id}.md").read_text(encoding="utf-8")
    recipe = client.get(f"api/opskrifter/{recipe_id}").json()
    assert recipe["retbillede"] == f"api/billeder/{recipe_id}.ret.jpg"
    assert client.get("api/opskrifter").json()[0]["billede"] == f"api/billeder/{recipe_id}.ret.jpg"


def test_the_area_can_be_on_a_later_original_image(client: TestClient, fake_reader: FakeReader, library_dir: Path) -> None:
    reading = read_with_area(client, fake_reader, {**LEFT_HALF, "billede": 2, "venstre": 0.5, "hoejre": 1.0}, jpeg(), red_and_blue())

    recipe_id = save(client, reading["id"], 1, BOLLER).json()["id"]

    red, green, blue = color_at_centre((library_dir / f"{recipe_id}.ret.jpg").read_bytes())
    assert blue > 200 and red < 60


def test_without_an_area_there_is_no_dish_photo(client: TestClient, fake_reader: FakeReader, library_dir: Path) -> None:
    reading = read_with_area(client, fake_reader, None)

    recipe_id = save(client, reading["id"], 1, BOLLER).json()["id"]

    assert not (library_dir / f"{recipe_id}.ret.jpg").exists()
    assert client.get(f"api/opskrifter/{recipe_id}").json()["retbillede"] is None


def test_the_area_survives_an_edit_during_the_review(client: TestClient, fake_reader: FakeReader, library_dir: Path) -> None:
    reading = read_with_area(client, fake_reader, LEFT_HALF)
    # Frontenden sender ikke området med, når den gemmer rettelser midlertidigt eller gemmer opskriften.
    edited = {**BOLLER, "titel": "Mormors boller i karry"}

    client.put(f"api/aflaesninger/{reading['id']}/udkast/1", json=edited)
    recipe_id = save(client, reading["id"], 1, edited).json()["id"]

    assert recipe_id == "mormors-boller-i-karry"
    assert (library_dir / "mormors-boller-i-karry.ret.jpg").is_file()


def test_an_area_on_an_image_that_does_not_exist_is_ignored(
    client: TestClient, fake_reader: FakeReader, library_dir: Path
) -> None:
    reading = read_with_area(client, fake_reader, {**LEFT_HALF, "billede": 3})

    response = save(client, reading["id"], 1, BOLLER)

    assert response.status_code == 200
    assert not list(library_dir.glob("*.ret.jpg"))


def test_the_area_is_shown_in_the_review(client: TestClient, fake_reader: FakeReader) -> None:
    reading = read_with_area(client, fake_reader, LEFT_HALF)

    assert reading["udkast"][0]["retbillede_omraade"] == LEFT_HALF
