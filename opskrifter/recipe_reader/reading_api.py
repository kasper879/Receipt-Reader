"""HTTP-API for aflæsninger, udkast og lighedstjek af titel."""

import threading
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from . import images
from .library import Library
from .reader import Udkast
from .readings import Reading, Readings, as_recipe

SimilarRecipes = Callable[[str | None, str | None], list[dict[str, Any]]]
"""Opskrifter med en titel, der ligner, bortset fra opskriften med det givne id."""


class SaveBody(BaseModel):
    udkast: Udkast
    gem_alligevel: bool = False


def similar_rejection(similar: list[dict[str, Any]]) -> JSONResponse:
    titles = ", ".join(f"„{item['titel']}“" for item in similar)
    return JSONResponse(
        {"detail": f"Der findes allerede en opskrift, der hedder {titles}.", "lignende": similar}, status_code=409
    )


def router(readings: Readings, library: Library, similar_recipes: SimilarRecipes, prepared: Callable[[UploadFile, int], bytes]) -> APIRouter:
    api = APIRouter(prefix="/api")
    saving = threading.Lock()

    @api.post("/aflaesninger")
    def start(billeder: list[UploadFile]) -> JSONResponse:
        """Gemmer originalbillederne og aflæser dem. Svaret er udkast, eller en ventende aflæsning (202)."""
        data = [prepared(upload, images.ORIGINAL_IMAGE_SIZE) for upload in billeder]
        reading = readings.start(data)
        return JSONResponse(reading_view(reading), status_code=200 if reading.status == "udkast" else 202)

    @api.get("/aflaesninger")
    def list_readings() -> list[dict[str, Any]]:
        return [reading_view(reading) for reading in readings.list()]

    @api.get("/aflaesninger/{reading_id}")
    def get_reading(reading_id: str) -> dict[str, Any]:
        return reading_view(readings.get(reading_id))

    @api.get("/aflaesninger/{reading_id}/billeder/{name}")
    def reading_image(reading_id: str, name: str) -> FileResponse:
        return FileResponse(readings.image(reading_id, name), media_type="image/jpeg")

    @api.put("/aflaesninger/{reading_id}/udkast/{nr}")
    def update_draft(reading_id: str, nr: int, udkast: Udkast) -> dict[str, Any]:
        readings.update_draft(reading_id, nr, udkast)
        return reading_view(readings.get(reading_id))

    @api.post("/aflaesninger/{reading_id}/udkast/{nr}/gem", response_model=None)
    def save_draft(reading_id: str, nr: int, body: SaveBody) -> dict[str, Any] | JSONResponse:
        """Gemmer udkastet som opskrift. Ligner titlen en anden, afvises det uden bekræftelse."""
        with saving:
            reading = readings.get(reading_id)
            reading.draft(nr)
            similar = similar_recipes(body.udkast.titel, None)
            if similar and not body.gem_alligevel:
                return similar_rejection(similar)
            originals = [readings.image(reading_id, name) for name in reading.billeder]
            # Et foto af retten på originalbillederne bliver retbillede, jf. ticket 13.
            dish_photo = readings.dish_photo(reading_id, nr, images.DISH_PHOTO_SIZE)
            recipe_id = library.create(as_recipe(body.udkast), originals, dish_photo)
            following = readings.remove_draft(reading_id, nr)
        return {"id": recipe_id, "naeste": following}

    @api.delete("/aflaesninger/{reading_id}/udkast/{nr}")
    def discard_draft(reading_id: str, nr: int) -> dict[str, Any]:
        return {"naeste": readings.remove_draft(reading_id, nr)}

    @api.post("/aflaesninger/{reading_id}/proev-igen")
    def retry(reading_id: str) -> dict[str, Any]:
        return reading_view(readings.retry(reading_id))

    @api.delete("/aflaesninger/{reading_id}")
    def discard(reading_id: str) -> dict[str, Any]:
        readings.discard(reading_id)
        return {}

    @api.get("/lighed")
    def similar(titel: str = "", undtagen: str | None = None) -> list[dict[str, Any]]:
        return similar_recipes(titel, undtagen)

    return api


def reading_view(reading: Reading) -> dict[str, Any]:
    base = f"api/aflaesninger/{quote(reading.id)}/billeder"
    return {
        "id": reading.id,
        "status": reading.status,
        "oprettet": reading.oprettet.isoformat(),
        "originalbilleder": [f"{base}/{quote(name)}" for name in reading.billeder],
        "udkast": [{"nr": draft.nr, **draft.udkast.model_dump()} for draft in reading.udkast],
        "forsoeg": reading.forsoeg,
        "naeste_forsoeg": reading.naeste_forsoeg.isoformat() if reading.naeste_forsoeg else None,
        "fejl": reading.fejl,
        "automatisk": reading.automatisk,
    }
