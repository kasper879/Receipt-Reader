from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .library import Entry, Library
from .reader import Reader, UnconfiguredReader
from .search_index import SearchIndex, Sorting
from .settings import Settings

STATIC_DIR = Path(__file__).parent / "static"


def create_app(settings: Settings, reader: Reader | None = None) -> FastAPI:
    library = Library(settings.library_dir)
    index = SearchIndex(settings.index_path, library, _summary)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        index.sync()
        yield

    app = FastAPI(title="Opskrifter", lifespan=lifespan)
    app.state.reader = reader or UnconfiguredReader()

    @app.get("/api/opskrifter")
    def list_recipes(q: str = "", sortering: Sorting = Sorting.NYESTE, tag: str | None = None) -> list[dict[str, Any]]:
        return index.search(q, sortering, tag)

    @app.get("/api/tags")
    def tags() -> list[str]:
        return index.tags()

    @app.get("/api/opskrifter/{recipe_id}")
    def get_recipe(recipe_id: str) -> dict[str, Any]:
        entry = library.get(recipe_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Opskriften findes ikke")
        return _details(entry)

    @app.get("/api/billeder/{name}")
    def image(name: str) -> FileResponse:
        path = library.image(name)
        if path is None:
            raise HTTPException(status_code=404, detail="Billedet findes ikke")
        return FileResponse(path)

    @app.get("/", include_in_schema=False)
    def front_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


def _common(entry: Entry) -> dict[str, Any]:
    """Felterne, som både listen og den enkelte opskrift har."""
    opskrift = entry.opskrift
    return {
        "id": entry.id,
        "titel": opskrift.titel or entry.id,
        "kilde": opskrift.kilde,
        "total": opskrift.total,
        "tags": opskrift.tags,
        "vurdering": opskrift.vurdering,
        "oprettet": opskrift.oprettet.isoformat() if opskrift.oprettet else None,
        "advarsel": opskrift.advarsel,
    }


def _summary(entry: Entry) -> dict[str, Any]:
    opskrift = entry.opskrift
    image = opskrift.retbillede or next(iter(opskrift.originalbilleder), None)
    return {**_common(entry), "billede": _image_url(image)}


def _details(entry: Entry) -> dict[str, Any]:
    opskrift = entry.opskrift
    return {
        **_common(entry),
        "portioner": opskrift.portioner,
        "forberedelse": opskrift.forberedelse,
        "retbillede": _image_url(opskrift.retbillede),
        "originalbilleder": [_image_url(name) for name in opskrift.originalbilleder],
        "ingredienser": [asdict(group) for group in opskrift.ingredienser],
        "trin": opskrift.trin,
        "noter": opskrift.noter,
        "raa": opskrift.raa,
    }


def _image_url(name: str | None) -> str | None:
    """Relativ URL, så billedet virker under Ingress' dynamiske sti."""
    return f"api/billeder/{quote(name)}" if name else None
