import json
import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_LIBRARY_DIR = Path("/share/opskrifter")
ADDON_OPTIONS = Path("/data/options.json")
DEFAULT_MODEL = "claude-opus-5-5"
"""Claude-modellen, der aflæser originalbillederne, når indstillingerne ikke angiver en anden."""
DEFAULT_SHOPPING_LIST = "todo.shopping_list"
"""Home Assistants indbyggede indkøbsliste."""
SUPERVISOR_API = "http://supervisor/core/api"
"""Home Assistants API, set fra en add-on med `homeassistant_api: true`."""


@dataclass(frozen=True)
class Settings:
    library_dir: Path
    index_path: Path
    api_key: str | None = field(default=None, repr=False)
    """API-nøglen til aflæsningstjenesten. Den er en hemmelighed og må aldrig logges."""
    model: str = DEFAULT_MODEL
    ha_url: str = SUPERVISOR_API
    ha_token: str | None = field(default=None, repr=False)
    """Tokenen til Home Assistants API, som Supervisor giver add-on'en. Den må aldrig logges."""
    shopping_list: str = DEFAULT_SHOPPING_LIST
    """Todo-listen i Home Assistant, som ingredienser lægges på."""

    @classmethod
    def from_environment(cls) -> "Settings":
        """Læser add-on'ens indstillinger. Miljøvariabler vinder, så appen også kan køres lokalt."""
        options: dict[str, str] = {}
        if ADDON_OPTIONS.exists():
            options = json.loads(ADDON_OPTIONS.read_text(encoding="utf-8"))
        library_dir = os.environ.get("RECIPE_LIBRARY_DIR") or options.get("biblioteksmappe") or DEFAULT_LIBRARY_DIR
        index_path = os.environ.get("RECIPE_INDEX_PATH") or "/data/index.sqlite"
        api_key = os.environ.get("RECIPE_API_KEY") or options.get("api_noegle") or None
        model = os.environ.get("RECIPE_MODEL") or options.get("model") or DEFAULT_MODEL
        # Lokalt kan RECIPE_HA_URL og et long-lived access token i RECIPE_HA_TOKEN bruges i stedet for Supervisor.
        ha_url = os.environ.get("RECIPE_HA_URL") or SUPERVISOR_API
        ha_token = os.environ.get("RECIPE_HA_TOKEN") or os.environ.get("SUPERVISOR_TOKEN") or None
        shopping_list = os.environ.get("RECIPE_SHOPPING_LIST") or options.get("indkoebsliste") or DEFAULT_SHOPPING_LIST
        return cls(
            library_dir=Path(library_dir),
            index_path=Path(index_path),
            api_key=api_key,
            model=model,
            ha_url=ha_url,
            ha_token=ha_token,
            shopping_list=shopping_list,
        )
