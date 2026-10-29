from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import images, reading_api, titles
from .library import Entry, HasWarning, Library, NotFound
from .reader import Reader, UnconfiguredReader
from .readings import ReadingNotFound, Readings
from .search_index import SearchIndex, Sorting
from .settings import Settings

STATIC_DIR = Path(__file__).parent / "static"


class RatingBody(BaseModel):
    vurdering: Annotated[int, Field(ge=1, le=5)] | None


def create_app(settings: Settings, reader: Reader | None = None) -> FastAPI:
    library = Library(settings.library_dir)
    index = SearchIndex(settings.index_path, library, _summary)
    readings = Readings(settings.library_dir, reader or UnconfiguredReader())

    def similar_recipes(title: str | None, except_id: str | None) -> list[dict[str, Any]]:
        """Opskrifter i biblioteket med en titel, der ligner. En fil med advarsel har ingen titel at sammenligne med."""
        return [
            {"id": item["id"], "titel": item["titel"], "oprettet": item["oprettet"]}
            for item in index.search(sorting=Sorting.ALFABETISK)
            if not item["advarsel"] and item["id"] != except_id and titles.similar(title or "", item["titel"])
        ]

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        index.sync()
        yield
        index.close()

    app = FastAPI(title="Opskrifter", lifespan=lifespan)
    app.include_router(reading_api.router(readings, library, similar_recipes, _prepared))

    @app.middleware("http")
    async def revalidate_frontend(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Frontenden og billederne hentes altid i nyeste version, fx efter en opdatering eller et skiftet retbillede."""
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith(("/static/", "/api/billeder/")):
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/api/opskrifter")
    def list_recipes(q: str = "", sortering: Sorting = Sorting.NYESTE, tag: str | None = None) -> list[dict[str, Any]]:
        return index.search(q, sortering, tag)

    @app.get("/api/tags")
    def tags() -> list[str]:
        return index.tags()

    @app.get("/api/opskrifter/{recipe_id}")
    def get_recipe(recipe_id: str) -> dict[str, Any]:
        return _details(_get(recipe_id))

    @app.put("/api/opskrifter/{recipe_id}/vurdering")
    def set_rating(recipe_id: str, body: RatingBody) -> dict[str, Any]:
        library.set_rating(recipe_id, body.vurdering)
        return _details(_get(recipe_id))

    @app.put("/api/opskrifter/{recipe_id}/retbillede")
    def set_dish_photo(recipe_id: str, billede: UploadFile) -> dict[str, Any]:
        _get(recipe_id)
        library.set_dish_photo(recipe_id, _prepared(billede, images.DISH_PHOTO_SIZE))
        return _details(_get(recipe_id))

    @app.delete("/api/opskrifter/{recipe_id}/retbillede")
    def remove_dish_photo(recipe_id: str) -> dict[str, Any]:
        library.remove_dish_photo(recipe_id)
        return _details(_get(recipe_id))

    @app.delete("/api/opskrifter/{recipe_id}")
    def trash(recipe_id: str) -> dict[str, str]:
        return {"papirkurv": library.trash(recipe_id)}

    @app.get("/api/papirkurv")
    def trashed() -> list[dict[str, str]]:
        return [{"id": item.id, "titel": item.titel, "slettet": item.slettet.date().isoformat()} for item in library.trashed()]

    @app.post("/api/papirkurv/{trash_id}/hent-tilbage")
    def restore(trash_id: str) -> dict[str, str]:
        return {"id": library.restore(trash_id)}

    @app.delete("/api/papirkurv/{trash_id}")
    def delete_permanently(trash_id: str) -> dict[str, str]:
        library.delete_permanently(trash_id)
        return {}

    def _get(recipe_id: str) -> Entry:
        entry = library.get(recipe_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Opskriften findes ikke")
        return entry

    @app.exception_handler(NotFound)
    def not_found(request: Request, error: NotFound) -> JSONResponse:
        return JSONResponse({"detail": "Opskriften findes ikke"}, status_code=404)

    @app.exception_handler(ReadingNotFound)
    def reading_not_found(request: Request, error: ReadingNotFound) -> JSONResponse:
        return JSONResponse({"detail": "Aflæsningen eller udkastet findes ikke"}, status_code=404)

    @app.exception_handler(HasWarning)
    def has_warning(request: Request, error: HasWarning) -> JSONResponse:
        return JSONResponse(
            {"detail": "Filen kunne ikke læses korrekt og kan kun rettes via Samba"}, status_code=409
        )

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


def _prepared(upload: UploadFile, longest_side: int) -> bytes:
    try:
        return images.prepare(upload.file.read(), longest_side)
    except images.InvalidImage as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


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
