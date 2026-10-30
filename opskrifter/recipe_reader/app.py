import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import images, reading_api, titles
from .library import Entry, HasWarning, Library, NotFound
from .reader import Reader, UnconfiguredReader
from .readings import PageFetcher, ReadingNotFound, Readings, as_recipe
from .search_index import SearchIndex, Sorting
from .settings import Settings
from .web_page import WebFetcher

STATIC_DIR = Path(__file__).parent / "static"

logger = logging.getLogger(__name__)


class RatingBody(BaseModel):
    vurdering: Annotated[int, Field(ge=1, le=5)] | None


RETRY_CHECK_SECONDS = 30.0
"""Hvor ofte baggrundsopgaven ser efter ventende aflæsninger, der skal prøves igen."""


def create_app(
    settings: Settings,
    reader: Reader | None = None,
    retry_check_seconds: float = RETRY_CHECK_SECONDS,
    fetcher: PageFetcher | None = None,
) -> FastAPI:
    library = Library(settings.library_dir)
    index = SearchIndex(settings.index_path, library, _summary)
    readings = Readings(settings.library_dir, reader or UnconfiguredReader(), fetcher or WebFetcher())

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
        retrying = asyncio.create_task(_retry_pending(readings, retry_check_seconds))
        yield
        retrying.cancel()
        with suppress(asyncio.CancelledError):
            await retrying
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

    @app.put("/api/opskrifter/{recipe_id}", response_model=None)
    def update_recipe(recipe_id: str, body: reading_api.SaveBody) -> dict[str, Any] | JSONResponse:
        """Opdaterer en gemt opskrift. Ligner titlen en anden opskrift, afvises det uden bekræftelse."""
        current = _get(recipe_id).opskrift
        # Advarslen gælder kun en ændret titel. Ellers skulle en opskrift, der blev gemt med "Gem alligevel",
        # bekræftes igen ved hver rettelse.
        title_changed = titles.normalize(body.udkast.titel or "") != titles.normalize(current.titel or "")
        similar = similar_recipes(body.udkast.titel, recipe_id) if title_changed else []
        if similar and not body.gem_alligevel:
            return reading_api.similar_rejection(similar)
        library.update(recipe_id, as_recipe(body.udkast))
        return _details(_get(recipe_id))

    @app.post("/api/opskrifter/{recipe_id}/originalbilleder")
    def add_originals(recipe_id: str, billeder: list[UploadFile]) -> dict[str, Any]:
        _get(recipe_id)
        library.add_originals(recipe_id, [_prepared(upload, images.ORIGINAL_IMAGE_SIZE) for upload in billeder])
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


async def _retry_pending(readings: Readings, interval: float) -> None:
    """Prøver ventende aflæsninger igen i baggrunden, også dem, der ventede, da appen blev startet."""
    while True:
        for reading_id in await run_in_threadpool(readings.due, datetime.now()):
            try:
                await run_in_threadpool(readings.retry, reading_id)
            except ReadingNotFound:
                pass  # Kasseret i mellemtiden.
            except Exception:
                logger.exception("Den ventende aflæsning %s kunne ikke prøves igen", reading_id)
        await asyncio.sleep(interval)


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
        "link": opskrift.link,
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
