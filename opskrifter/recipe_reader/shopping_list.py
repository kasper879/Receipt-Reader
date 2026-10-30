"""Indkøbslisten: lægger ingredienser på en todo-liste i Home Assistant via Supervisor-API'et.

Add-on'en får en token fra Supervisor, når `homeassistant_api` er slået til i config.yaml.
Tokenen er en hemmelighed og logges aldrig. Uden token, fx når appen køres lokalt, er der
ingen indkøbsliste, og frontenden skjuler knappen.
"""

import logging
from typing import Protocol
from urllib.parse import quote

import httpx2

from .settings import Settings

logger = logging.getLogger(__name__)

TIMEOUT = httpx2.Timeout(10.0)


class ShoppingListError(Exception):
    """Varerne kunne ikke lægges på listen. Beskeden kan vises for brugeren."""


class ShoppingList(Protocol):
    available: bool
    entity_id: str

    def add(self, items: list[str], description: str | None) -> None: ...


class NoShoppingList:
    """Uden Home Assistant er der ingen indkøbsliste."""

    available = False

    def __init__(self, entity_id: str) -> None:
        self.entity_id = entity_id

    def add(self, items: list[str], description: str | None) -> None:
        raise ShoppingListError("Indkøbslisten kræver, at appen kører i Home Assistant.")


class HomeAssistantShoppingList:
    available = True

    def __init__(self, base_url: str, token: str, entity_id: str, client: httpx2.Client | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.entity_id = entity_id
        self._client = client or httpx2.Client(timeout=TIMEOUT)
        self._headers = {"authorization": f"Bearer {token}"}

    def __repr__(self) -> str:
        return f"HomeAssistantShoppingList(entity_id={self.entity_id!r})"

    def add(self, items: list[str], description: str | None) -> None:
        """Lægger hver vare på listen. Listen kontrolleres først, så varer ikke forsvinder i en liste, der ikke findes."""
        self._request("GET", f"/states/{quote(self.entity_id)}")
        for item in items:
            body = {"entity_id": self.entity_id, "item": item, **({"description": description} if description else {})}
            self._request("POST", "/services/todo/add_item", body)
        logger.info("%d varer lagt på indkøbslisten %s", len(items), self.entity_id)

    def _request(self, method: str, path: str, body: dict[str, str] | None = None) -> None:
        try:
            response = self._client.request(method, f"{self.base_url}{path}", headers=self._headers, json=body)
        except httpx2.TransportError as error:
            logger.warning("Home Assistant svarer ikke (%s)", type(error).__name__)
            raise ShoppingListError("Home Assistant svarer ikke lige nu. Prøv igen om lidt.") from error
        if response.status_code in (401, 403):
            raise ShoppingListError("Appen har ikke adgang til Home Assistant. Genstart add-on'en, og prøv igen.")
        if response.status_code == 404 or response.status_code == 400:
            raise ShoppingListError(
                f"Indkøbslisten {self.entity_id} findes ikke i Home Assistant. Ret indstillingen indkoebsliste i add-on'en."
            )
        if response.status_code >= 300:
            logger.warning("Home Assistant svarede %s på %s %s", response.status_code, method, path)
            raise ShoppingListError(f"Home Assistant svarede med fejl {response.status_code}. Prøv igen om lidt.")


def shopping_list_from_settings(settings: Settings) -> ShoppingList:
    if not settings.ha_token:
        return NoShoppingList(settings.shopping_list)
    return HomeAssistantShoppingList(settings.ha_url, settings.ha_token, settings.shopping_list)
