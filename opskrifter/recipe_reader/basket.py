"""Indkøbskurven: ingredienser fra flere opskrifter, lagt sammen, før de sendes til indkøbslisten.

Kurven er fælles for husstanden og gemmes som JSON i biblioteksmappen, så den overlever en genstart.
Mængderne er allerede omregnet til de valgte portioner, når de lægges i kurven.
"""

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .files import write_atomically
from .recipe_format import Ingredient, Quantity, format_quantity

logger = logging.getLogger(__name__)

FILE = ".indkoebskurv.json"


@dataclass
class BasketRecipe:
    id: str
    titel: str
    portioner: int | None
    varer: list[Ingredient]


@dataclass
class BasketLine:
    """Én vare i kurven: ens ingredienser fra en eller flere opskrifter, lagt sammen."""

    noegle: str
    maengde: Quantity | None
    enhed: str | None
    navn: str
    opskrifter: list[str] = field(default_factory=list)
    """Titlerne på opskrifterne, varen er til."""

    @property
    def tekst(self) -> str:
        parts = [format_quantity(self.maengde) if self.maengde is not None else None, self.enhed, self.navn]
        return " ".join(part for part in parts if part)


def key(item: Ingredient) -> str:
    """Ens navn og enhed lægges sammen. En ingrediens uden mængde, fx "peber", lægges ikke sammen med "1 tsk peber"."""
    name = " ".join(item.navn.split()).casefold()
    unit = (item.enhed or "").casefold()
    return f"{name}|{unit}|{'' if item.maengde is None else 'm'}"


def combine(recipes: list[BasketRecipe]) -> list[BasketLine]:
    """Lægger ens ingredienser sammen i den rækkefølge, de først optræder."""
    lines: dict[str, BasketLine] = {}
    for recipe in recipes:
        for item in recipe.varer:
            line = lines.get(key(item))
            if line is None:
                line = lines[key(item)] = BasketLine(key(item), item.maengde, item.enhed, " ".join(item.navn.split()))
            elif item.maengde is not None and line.maengde is not None:
                line.maengde += item.maengde
            if recipe.titel not in line.opskrifter:
                line.opskrifter.append(recipe.titel)
    return list(lines.values())


class Basket:
    def __init__(self, library_dir: Path) -> None:
        self.path = library_dir / FILE
        self._lock = threading.Lock()

    def recipes(self) -> list[BasketRecipe]:
        with self._lock:
            return self._read()

    def put(self, recipe: BasketRecipe) -> None:
        """Lægger opskriften i kurven. Ligger den der allerede, erstattes dens varer."""
        with self._lock:
            recipes = self._read()
            existing = next((i for i, current in enumerate(recipes) if current.id == recipe.id), None)
            if existing is None:
                recipes.append(recipe)
            else:
                recipes[existing] = recipe
            self._write(recipes)

    def remove(self, recipe_ids: list[str]) -> None:
        with self._lock:
            self._write([recipe for recipe in self._read() if recipe.id not in recipe_ids])

    def _read(self) -> list[BasketRecipe]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return [
                BasketRecipe(
                    id=recipe["id"],
                    titel=recipe["titel"],
                    portioner=recipe.get("portioner"),
                    varer=[Ingredient(item.get("maengde"), item.get("enhed"), item["navn"]) for item in recipe["varer"]],
                )
                for recipe in data["opskrifter"]
            ]
        except (ValueError, KeyError, TypeError):
            logger.warning("Indkøbskurven i %s kunne ikke læses og starter forfra", self.path.name)
            return []

    def _write(self, recipes: list[BasketRecipe]) -> None:
        data = {"opskrifter": [asdict(recipe) for recipe in recipes]}
        write_atomically(self.path, json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
