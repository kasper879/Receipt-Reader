"""Papirkurv: slet, hent tilbage og slet endeligt."""

from collections.abc import Callable
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

WriteFile = Callable[[str, str | bytes], Path]

KAGE = "---\ntitel: Kage\ntags: [kage]\nretbillede: kage.ret.jpg\noriginalbilleder: [kage.1.jpg, kage.2.jpg]\n---\n\nTekst\n"


def titles(client: TestClient, **params: str) -> list[str]:
    return [item["titel"] for item in client.get("api/opskrifter", params=params).json()]


def files_in(folder: Path) -> list[str]:
    return sorted(str(p.relative_to(folder)).replace("\\", "/") for p in folder.rglob("*") if p.is_file())


def write_kage(write_file: WriteFile) -> None:
    write_file("kage.md", KAGE)
    for name in ["kage.ret.jpg", "kage.1.jpg", "kage.2.jpg"]:
        write_file(name, name.encode())


def test_delete_moves_the_file_and_its_images_to_the_trash(
    client: TestClient, write_file: WriteFile, library_dir: Path
) -> None:
    write_kage(write_file)
    write_file("kagemand.md", "---\ntitel: Kagemand\n---\n")
    write_file("kagemand.1.jpg", b"andet billede")

    response = client.delete("api/opskrifter/kage")

    assert response.status_code == 200
    assert titles(client) == ["Kagemand"]
    assert titles(client, q="kage") == ["Kagemand"]
    assert titles(client, tag="kage") == []
    assert client.get("api/opskrifter/kage").status_code == 404
    assert files_in(library_dir) == [
        ".papirkurv/kage/.slettet",
        ".papirkurv/kage/kage.1.jpg",
        ".papirkurv/kage/kage.2.jpg",
        ".papirkurv/kage/kage.md",
        ".papirkurv/kage/kage.ret.jpg",
        "kagemand.1.jpg",
        "kagemand.md",
    ]
    assert (library_dir / ".papirkurv" / "kage" / "kage.md").read_text(encoding="utf-8") == KAGE


def test_the_trash_lists_title_and_date_of_deletion(client: TestClient, write_file: WriteFile) -> None:
    write_kage(write_file)
    client.delete("api/opskrifter/kage")

    assert client.get("api/papirkurv").json() == [
        {"id": "kage", "titel": "Kage", "slettet": date.today().isoformat()}
    ]


def test_restore_moves_the_file_and_images_back(client: TestClient, write_file: WriteFile, library_dir: Path) -> None:
    write_kage(write_file)
    client.delete("api/opskrifter/kage")

    response = client.post("api/papirkurv/kage/hent-tilbage")

    assert response.status_code == 200
    assert response.json() == {"id": "kage"}
    assert files_in(library_dir) == ["kage.1.jpg", "kage.2.jpg", "kage.md", "kage.ret.jpg"]
    assert (library_dir / "kage.md").read_text(encoding="utf-8") == KAGE
    assert titles(client, tag="kage") == ["Kage"]
    assert client.get("api/papirkurv").json() == []


def test_restore_gets_a_new_name_when_the_old_one_is_taken(
    client: TestClient, write_file: WriteFile, library_dir: Path
) -> None:
    write_kage(write_file)
    client.delete("api/opskrifter/kage")
    write_file("kage.md", "---\ntitel: Ny kage\noriginalbilleder: [kage.1.jpg]\n---\n")
    write_file("kage.1.jpg", b"den nye kages billede")

    response = client.post("api/papirkurv/kage/hent-tilbage")

    assert response.json() == {"id": "kage-2"}
    assert files_in(library_dir) == ["kage-2.1.jpg", "kage-2.2.jpg", "kage-2.md", "kage-2.ret.jpg", "kage.1.jpg", "kage.md"]
    assert (library_dir / "kage.1.jpg").read_bytes() == b"den nye kages billede"
    assert (library_dir / "kage-2.1.jpg").read_bytes() == b"kage.1.jpg"
    restored = client.get("api/opskrifter/kage-2").json()
    assert restored["titel"] == "Kage"
    assert restored["retbillede"] == "api/billeder/kage-2.ret.jpg"
    assert restored["originalbilleder"] == ["api/billeder/kage-2.1.jpg", "api/billeder/kage-2.2.jpg"]
    assert client.get(restored["retbillede"]).content == b"kage.ret.jpg"


def test_deleting_the_same_name_twice_keeps_both_in_the_trash(client: TestClient, write_file: WriteFile) -> None:
    write_file("kage.md", "---\ntitel: Første kage\n---\n")
    client.delete("api/opskrifter/kage")
    write_file("kage.md", "---\ntitel: Anden kage\n---\n")
    client.delete("api/opskrifter/kage")

    trash = client.get("api/papirkurv").json()

    assert sorted((item["id"], item["titel"]) for item in trash) == [("kage", "Første kage"), ("kage-2", "Anden kage")]


def test_delete_permanently_removes_the_files(client: TestClient, write_file: WriteFile, library_dir: Path) -> None:
    write_kage(write_file)
    client.delete("api/opskrifter/kage")

    assert client.delete("api/papirkurv/kage").status_code == 200

    assert files_in(library_dir) == []
    assert client.get("api/papirkurv").json() == []


def test_a_file_that_cannot_be_read_can_be_deleted_and_restored_unchanged(
    client: TestClient, write_file: WriteFile, library_dir: Path
) -> None:
    broken = "---\ntitel: [Pasta\n---\n"
    write_file("pasta.md", broken)

    assert client.delete("api/opskrifter/pasta").status_code == 200
    assert client.get("api/papirkurv").json()[0]["titel"] == "pasta"
    client.post("api/papirkurv/pasta/hent-tilbage")

    assert (library_dir / "pasta.md").read_text(encoding="utf-8") == broken


def test_unknown_ids_give_404(client: TestClient) -> None:
    assert client.delete("api/opskrifter/findes-ikke").status_code == 404
    assert client.post("api/papirkurv/findes-ikke/hent-tilbage").status_code == 404
    assert client.delete("api/papirkurv/findes-ikke").status_code == 404
    assert client.delete("api/papirkurv/..").status_code == 404


def test_a_trash_folder_without_a_date_of_deletion_is_still_listed(
    client: TestClient, write_file: WriteFile, library_dir: Path
) -> None:
    write_kage(write_file)
    client.delete("api/opskrifter/kage")
    (library_dir / ".papirkurv" / "kage" / ".slettet").write_text("ikke en dato", encoding="utf-8")
    write_file("bolle.md", "---\ntitel: Bolle\n---\n")
    client.delete("api/opskrifter/bolle")
    (library_dir / ".papirkurv" / "bolle" / ".slettet").unlink()

    response = client.get("api/papirkurv")

    assert response.status_code == 200
    assert sorted(item["titel"] for item in response.json()) == ["Bolle", "Kage"]
