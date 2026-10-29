"""Retbillede: upload, skift og fjern."""

from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient

from tests.images import jpeg, size_of

WriteFile = Callable[[str, str | bytes], Path]

KAGE = "---\ntitel: Kage\noriginalbilleder: [kage.1.jpg]\n---\n\nTekst\n"


def upload(client: TestClient, recipe_id: str, data: bytes) -> int:
    files = {"billede": ("IMG_0001.JPG", data, "image/jpeg")}
    return client.put(f"api/opskrifter/{recipe_id}/retbillede", files=files).status_code


def test_upload_saves_the_image_next_to_the_file_and_sets_the_field(
    client: TestClient, write_file: WriteFile, library_dir: Path
) -> None:
    path = write_file("kage.md", KAGE)

    assert upload(client, "kage", jpeg()) == 200

    assert (library_dir / "kage.ret.jpg").is_file()
    assert path.read_text(encoding="utf-8") == (
        "---\ntitel: Kage\noriginalbilleder: [kage.1.jpg]\nretbillede: kage.ret.jpg\n---\n\nTekst\n"
    )
    [item] = client.get("api/opskrifter").json()
    assert item["billede"] == "api/billeder/kage.ret.jpg"
    assert client.get("api/opskrifter/kage").json()["retbillede"] == "api/billeder/kage.ret.jpg"


def test_large_photos_are_scaled_down_and_rotated(client: TestClient, write_file: WriteFile, library_dir: Path) -> None:
    write_file("kage.md", KAGE)

    # Orientering 6: telefonen blev holdt på højkant, så billedet skal drejes 90°.
    upload(client, "kage", jpeg(4000, 3000, orientation=6))

    assert size_of((library_dir / "kage.ret.jpg").read_bytes()) == (1200, 1600)


def test_change_replaces_the_old_image(client: TestClient, write_file: WriteFile, library_dir: Path) -> None:
    write_file("kage.md", "---\ntitel: Kage\nretbillede: kage-gammel.png\n---\n")
    write_file("kage-gammel.png", b"gammelt billede")

    assert upload(client, "kage", jpeg(color="blue")) == 200

    assert not (library_dir / "kage-gammel.png").exists()
    assert client.get("api/opskrifter/kage").json()["retbillede"] == "api/billeder/kage.ret.jpg"


def test_change_with_the_same_name_serves_the_new_image(client: TestClient, write_file: WriteFile) -> None:
    write_file("kage.md", KAGE)
    upload(client, "kage", jpeg(color="red"))
    first = client.get("api/billeder/kage.ret.jpg")

    upload(client, "kage", jpeg(color="blue"))
    second = client.get("api/billeder/kage.ret.jpg")

    assert first.content != second.content
    assert second.headers["cache-control"] == "no-cache"


def test_remove_falls_back_to_the_original_image(client: TestClient, write_file: WriteFile, library_dir: Path) -> None:
    path = write_file("kage.md", KAGE)
    upload(client, "kage", jpeg())

    assert client.delete("api/opskrifter/kage/retbillede").status_code == 200

    assert not (library_dir / "kage.ret.jpg").exists()
    assert path.read_text(encoding="utf-8") == KAGE
    assert client.get("api/opskrifter").json()[0]["billede"] == "api/billeder/kage.1.jpg"
    assert client.get("api/opskrifter/kage").json()["retbillede"] is None


def test_an_original_image_is_never_deleted_as_the_old_dish_photo(
    client: TestClient, write_file: WriteFile, library_dir: Path
) -> None:
    write_file("kage.md", "---\ntitel: Kage\nretbillede: kage.1.jpg\noriginalbilleder: [kage.1.jpg]\n---\n")
    write_file("kage.1.jpg", jpeg())

    client.delete("api/opskrifter/kage/retbillede")

    assert (library_dir / "kage.1.jpg").is_file()


def test_a_file_that_is_not_an_image_is_rejected(client: TestClient, write_file: WriteFile) -> None:
    path = write_file("kage.md", KAGE)

    assert upload(client, "kage", b"ikke et billede") == 422
    assert path.read_text(encoding="utf-8") == KAGE


def test_a_file_that_cannot_be_read_cannot_get_a_dish_photo(
    client: TestClient, write_file: WriteFile, library_dir: Path
) -> None:
    broken = "---\ntitel: [Pasta\n---\n"
    path = write_file("pasta.md", broken)

    assert upload(client, "pasta", jpeg()) == 409
    assert path.read_text(encoding="utf-8") == broken
    assert not (library_dir / "pasta.ret.jpg").exists()
