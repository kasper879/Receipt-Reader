import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_LIBRARY_DIR = Path("/share/opskrifter")
ADDON_OPTIONS = Path("/data/options.json")


@dataclass(frozen=True)
class Settings:
    library_dir: Path
    index_path: Path

    @classmethod
    def from_environment(cls) -> "Settings":
        """Læser add-on'ens indstillinger. Miljøvariabler vinder, så appen også kan køres lokalt."""
        options: dict[str, str] = {}
        if ADDON_OPTIONS.exists():
            options = json.loads(ADDON_OPTIONS.read_text(encoding="utf-8"))
        library_dir = os.environ.get("RECIPE_LIBRARY_DIR") or options.get("biblioteksmappe") or DEFAULT_LIBRARY_DIR
        index_path = os.environ.get("RECIPE_INDEX_PATH") or "/data/index.sqlite"
        return cls(library_dir=Path(library_dir), index_path=Path(index_path))
