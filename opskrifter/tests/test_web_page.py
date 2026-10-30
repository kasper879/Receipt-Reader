"""Hentning af en hjemmeside med en opskrift, mod en mocket HTTP-klient."""

import json
import socket
from collections.abc import Callable
from typing import Any

import httpx2
import pytest

from recipe_reader.reader import RejectedError, TechnicalError
from recipe_reader.web_page import InvalidLink, WebFetcher, check_link
from tests.images import jpeg

RECIPE_LD = {
    "@context": "https://schema.org",
    "@graph": [
        {"@type": "WebPage", "name": "Boller i karry - Madens Verden"},
        {
            "@type": ["Recipe"],
            "name": "Boller i karry",
            "image": [{"@type": "ImageObject", "url": "/billeder/boller.jpg"}],
            "recipeIngredient": ["400 g hakket kalv og svin", "2 tsk karry"],
        },
    ],
}

PAGE = f"""<!doctype html><html><head>
<title>Boller i karry - Madens Verden</title>
<meta property="og:image" content="https://madensverden.test/og.jpg">
<script type="application/ld+json">{json.dumps(RECIPE_LD)}</script>
<script>var tracking = "ikke med";</script><style>.x {{ color: red }}</style>
</head><body><nav>Menu</nav><h1>Boller i karry</h1><p>Kødbollerne laves af hakket kalv og svin.</p>
<ul><li>400 g hakket kalv og svin</li></ul></body></html>"""


def public(host: str, *args: Any, **kwargs: Any) -> list[Any]:
    """Navneopslag, hvor alle testværter er offentlige, undtagen `intern.test`, som peger på hjemmenetværket."""
    address = "192.168.1.20" if host == "intern.test" else "93.184.216.34"
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]


def fetcher(handler: Callable[[httpx2.Request], httpx2.Response]) -> WebFetcher:
    return WebFetcher(client=httpx2.Client(transport=httpx2.MockTransport(handler)), resolve=public)


def html(body: str, status: int = 200, **headers: str) -> httpx2.Response:
    return httpx2.Response(status, headers={"content-type": "text/html; charset=utf-8", **headers}, content=body.encode("utf-8"))


def test_the_recipe_data_title_image_and_text_are_extracted() -> None:
    page = fetcher(lambda request: html(PAGE)).page("https://madensverden.test/boller-i-karry/")

    assert page.url == "https://madensverden.test/boller-i-karry/"
    assert page.title == "Boller i karry - Madens Verden"
    assert [item["name"] for item in page.recipes] == ["Boller i karry"]
    assert page.image_url == "https://madensverden.test/billeder/boller.jpg"
    assert "Kødbollerne laves af hakket kalv og svin." in page.text
    assert "tracking" not in page.text and "color: red" not in page.text


def test_without_recipe_data_the_page_image_is_used() -> None:
    page = fetcher(lambda request: html('<html><head><meta property="og:image" content="/og.jpg"></head><body>Tekst</body></html>')).page(
        "https://kogebog.test/opskrift"
    )

    assert page.recipes == []
    assert page.image_url == "https://kogebog.test/og.jpg"


def test_redirects_are_followed() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/gammel":
            return httpx2.Response(301, headers={"location": "/ny"})
        return html("<html><body>Ny side</body></html>")

    page = fetcher(handler).page("https://kogebog.test/gammel")

    assert page.url == "https://kogebog.test/ny"
    assert "Ny side" in page.text


@pytest.mark.parametrize("link", ["ftp://kogebog.test/x", "kogebog.test/opskrift", "https://", "javascript:alert(1)", ""])
def test_only_http_and_https_links_are_accepted(link: str) -> None:
    with pytest.raises(InvalidLink):
        check_link(link)


@pytest.mark.parametrize(
    "link", ["http://localhost:8123/", "http://127.0.0.1/", "http://[::1]/", "http://intern.test/", "http://10.0.0.5/", "http://homeassistant.local/"]
)
def test_addresses_on_the_home_network_are_refused(link: str) -> None:
    calls: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(str(request.url))
        return html("hemmeligt")

    with pytest.raises(RejectedError):
        fetcher(handler).page(link)

    assert calls == []


def test_a_redirect_to_the_home_network_is_refused() -> None:
    calls: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(request.url.host)
        return httpx2.Response(302, headers={"location": "http://intern.test/admin"})

    with pytest.raises(RejectedError):
        fetcher(handler).page("https://kogebog.test/")

    assert calls == ["kogebog.test"]


@pytest.mark.parametrize("status", [404, 410, 403])
def test_a_page_that_does_not_exist_waits_for_the_user(status: int) -> None:
    with pytest.raises(RejectedError):
        fetcher(lambda request: html("findes ikke", status)).page("https://kogebog.test/x")


@pytest.mark.parametrize("status", [500, 503, 429])
def test_server_errors_are_technical_errors(status: int) -> None:
    with pytest.raises(TechnicalError) as raised:
        fetcher(lambda request: html("fejl", status)).page("https://kogebog.test/x")

    assert raised.value.retry_automatically


def test_network_errors_are_technical_errors() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("ingen forbindelse")

    with pytest.raises(TechnicalError) as raised:
        fetcher(handler).page("https://kogebog.test/x")

    assert raised.value.retry_automatically


def test_a_page_that_is_not_html_waits_for_the_user() -> None:
    response = httpx2.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF")

    with pytest.raises(RejectedError):
        fetcher(lambda request: response).page("https://kogebog.test/opskrift.pdf")


def test_a_page_larger_than_five_megabytes_is_refused() -> None:
    huge = "<html><body>" + "x" * (6 * 1024 * 1024) + "</body></html>"

    with pytest.raises(RejectedError):
        fetcher(lambda request: html(huge)).page("https://kogebog.test/stor")


def test_an_image_is_fetched_from_a_public_address() -> None:
    data = jpeg()
    image = fetcher(lambda request: httpx2.Response(200, headers={"content-type": "image/jpeg"}, content=data)).image(
        "https://kogebog.test/boller.jpg"
    )

    assert image == data


def test_an_image_on_the_home_network_is_refused() -> None:
    with pytest.raises(RejectedError):
        fetcher(lambda request: httpx2.Response(200, headers={"content-type": "image/jpeg"}, content=jpeg())).image("http://intern.test/x.jpg")
