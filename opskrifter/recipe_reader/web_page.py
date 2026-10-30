"""Henter en hjemmeside med en opskrift: struktureret data (schema.org Recipe), titel, billede og tekst.

Add-on'en kører på hjemmenetværket, så der hentes kun fra offentlige adresser. Værter som
`localhost`, `homeassistant.local` og private IP-adresser afvises, også efter en omdirigering.
"""

import ipaddress
import json
import socket
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx2

from .reader import RejectedError, TechnicalError

MAX_BYTES = 5 * 1024 * 1024
"""Den største side eller det største billede, der hentes."""
MAX_TEXT = 20_000
"""Så meget af sidens tekst sendes med til aflæsningen."""
MAX_REDIRECTS = 5
TIMEOUT = httpx2.Timeout(20.0, connect=10.0)
USER_AGENT = "Opskrifter (Home Assistant add-on; https://github.com/kasper879/Receipt-Reader)"

LOCAL_SUFFIXES = (".local", ".localhost", ".internal", ".lan", ".home", ".home.arpa", ".localdomain")

Resolve = Callable[..., list[Any]]


class InvalidLink(ValueError):
    """Linket er ikke en http- eller https-adresse."""


@dataclass
class PageContent:
    url: str
    """Adressen efter eventuelle omdirigeringer."""
    title: str | None
    recipes: list[dict[str, Any]] = field(default_factory=list)
    """Opskrifter som struktureret data (schema.org Recipe fra JSON-LD), hvis siden har dem."""
    image_url: str | None = None
    text: str = ""


def check_link(link: str) -> str:
    """Linket uden mellemrum, hvis det er en http- eller https-adresse med en vært."""
    link = link.strip()
    parts = urlsplit(link)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise InvalidLink("Indsæt et link, der starter med https://")
    return link


class WebFetcher:
    def __init__(self, client: httpx2.Client | None = None, resolve: Resolve = socket.getaddrinfo) -> None:
        self.client = client or httpx2.Client(timeout=TIMEOUT, headers={"user-agent": USER_AGENT})
        self.resolve = resolve

    def page(self, link: str) -> PageContent:
        url, data, content_type = self._get(link)
        if "html" not in content_type:
            raise RejectedError("Linket peger ikke på en hjemmeside. Brug linket til selve opskriften.")
        extractor = _Extractor()
        extractor.feed(data.decode(_charset(content_type), errors="replace"))
        recipes = [recipe for block in extractor.json_ld for recipe in _recipes(block)]
        image = next((image for recipe in recipes if (image := _image(recipe.get("image")))), None) or extractor.og_image
        return PageContent(
            url=url,
            title=extractor.title.strip() or None,
            recipes=recipes,
            image_url=urljoin(url, image) if image else None,
            text=extractor.text()[:MAX_TEXT],
        )

    def image(self, link: str) -> bytes:
        _, data, content_type = self._get(link)
        if not content_type.startswith("image/"):
            raise RejectedError("Billedet på siden kunne ikke hentes.")
        return data

    def _get(self, link: str) -> tuple[str, bytes, str]:
        """Henter en adresse og følger omdirigeringer. Hver adresse kontrolleres, før den hentes."""
        url = check_link(link)
        for _ in range(MAX_REDIRECTS + 1):
            self._check_public(url)
            try:
                with self.client.stream("GET", url, follow_redirects=False) as response:
                    if response.is_redirect and "location" in response.headers:
                        url = urljoin(url, response.headers["location"])
                        continue
                    _check_status(response.status_code)
                    return url, _read_limited(response.iter_bytes()), response.headers.get("content-type", "").lower()
            except httpx2.TransportError as error:
                raise TechnicalError("Siden kunne ikke hentes lige nu. Den prøves igen senere.") from error
        raise RejectedError("Siden omdirigerer for mange gange.")

    def _check_public(self, url: str) -> None:
        host = (urlsplit(url).hostname or "").lower().rstrip(".")
        try:
            literal = ipaddress.ip_address(host)
        except ValueError:
            literal = None
        if literal is not None:
            if not literal.is_global:
                raise RejectedError("Appen henter kun sider fra internettet, ikke fra hjemmenetværket.")
            return
        if host == "localhost" or host.endswith(LOCAL_SUFFIXES) or "." not in host:
            raise RejectedError("Appen henter kun sider fra internettet, ikke fra hjemmenetværket.")
        try:
            addresses = {info[4][0] for info in self.resolve(host, None)}
        except (socket.gaierror, UnicodeError) as error:
            raise TechnicalError("Siden kunne ikke findes lige nu. Den prøves igen senere.") from error
        if not addresses or not all(ipaddress.ip_address(address.split("%")[0]).is_global for address in addresses):
            raise RejectedError("Appen henter kun sider fra internettet, ikke fra hjemmenetværket.")


def _check_status(status: int) -> None:
    if status == 429 or status == 408 or status >= 500:
        raise TechnicalError(f"Siden svarede med fejl {status}. Den prøves igen senere.")
    if status >= 400:
        raise RejectedError(f"Siden kunne ikke hentes (fejl {status}). Tjek linket.")


def _read_limited(chunks: Iterator[bytes]) -> bytes:
    data = bytearray()
    for chunk in chunks:
        data += chunk
        if len(data) > MAX_BYTES:
            raise RejectedError("Siden er for stor til at blive hentet.")
    return bytes(data)


def _charset(content_type: str) -> str:
    for part in content_type.split(";"):
        key, _, value = part.strip().partition("=")
        if key == "charset" and value:
            return value.strip("\"'")
    return "utf-8"


def _recipes(block: Any) -> Iterator[dict[str, Any]]:
    """Alle schema.org Recipe-objekter i en JSON-LD-blok, også inde i @graph og lister."""
    if isinstance(block, list):
        for item in block:
            yield from _recipes(item)
    elif isinstance(block, dict):
        kinds = block.get("@type")
        if "Recipe" in (kinds if isinstance(kinds, list) else [kinds]):
            yield block
        yield from _recipes(block.get("@graph"))


def _image(value: Any) -> str | None:
    """Et billede fra schema.org: en adresse, en liste af dem eller et ImageObject."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return next((image for item in value if (image := _image(item))), None)
    if isinstance(value, dict):
        return _image(value.get("url") or value.get("contentUrl"))
    return None


class _Extractor(HTMLParser):
    """Titel, og:image, JSON-LD og den synlige tekst fra en side."""

    SKIP = {"script", "style", "noscript", "template", "svg", "head"}
    BLOCKS = {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "ol", "ul"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.og_image: str | None = None
        self.json_ld: list[Any] = []
        self._parts: list[str] = []
        self._stack: list[str] = []
        self._ld: list[str] | None = None
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "meta" and values.get("property") == "og:image" and not self.og_image:
            self.og_image = values.get("content") or None
        if tag == "script" and values.get("type", "").lower() == "application/ld+json":
            self._ld = []
        if tag == "title":
            self._in_title = True
        if tag in self.SKIP:
            self._stack.append(tag)
        if tag in self.BLOCKS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._ld is not None:
            try:
                self.json_ld.append(json.loads("".join(self._ld)))
            except ValueError:
                pass
            self._ld = None
        if tag == "title":
            self._in_title = False
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()
        if tag in self.BLOCKS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ld is not None:
            self._ld.append(data)
        elif self._in_title:
            self.title += data
        elif not self._stack:
            self._parts.append(data)

    def text(self) -> str:
        lines = (" ".join(line.split()) for line in "".join(self._parts).splitlines())
        return "\n".join(line for line in lines if line)
