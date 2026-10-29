"""Den statiske frontend serveres af samme proces og virker under Ingress' dynamiske sti."""

import re
from pathlib import PurePosixPath

from fastapi.testclient import TestClient


def test_front_page_is_served(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<title>Opskrifter</title>" in response.text


def test_front_page_only_uses_relative_urls(client: TestClient) -> None:
    html = client.get("/").text

    urls = re.findall(r'(?:src|href)="([^"]*)"', html)

    assert urls
    assert all(not url.startswith(("/", "http:", "https:")) for url in urls), urls


def test_assets_and_fonts_are_served_without_external_calls(client: TestClient) -> None:
    css = client.get("static/style.css")
    fonts = re.findall(r'url\("?([^")]+)"?\)', css.text)

    assert css.status_code == 200
    assert {"Fraunces", "Inter", "Caveat"} <= set(re.findall(r'font-family:\s*"?(\w+)', css.text))
    assert fonts
    for font in fonts:
        assert not font.startswith(("/", "http:", "https:")), font
        assert client.get(f"static/{font}").status_code == 200, font
    assert client.get("static/app.js").status_code == 200


def test_the_frontend_is_revalidated_after_an_update(client: TestClient) -> None:
    for url in ["/", "static/app.js", "static/style.css"]:
        assert client.get(url).headers["cache-control"] == "no-cache", url


def test_javascript_modules_are_served_and_only_import_relatively(client: TestClient) -> None:
    pending, seen = ["static/app.js"], set()
    while pending:
        url = pending.pop()
        seen.add(url)
        response = client.get(url)
        assert response.status_code == 200, url
        for target in re.findall(r'from\s+"([^"]+)"', response.text):
            assert target.startswith("./"), (url, target)
            resolved = str(PurePosixPath(url).parent / target[2:])
            if resolved not in seen:
                pending.append(resolved)

    assert len(seen) > 1
