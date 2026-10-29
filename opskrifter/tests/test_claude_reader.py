"""Claude-aflæseren mod en mocket HTTP-klient: skemavalidering og fejlklassificering.

Adapteren testes ikke mod den rigtige tjeneste her. Den testes manuelt, jf. ticket 06.
"""

import base64
import json
import logging
from collections.abc import Callable
from typing import Any

import anthropic
import httpx2
import pytest

from recipe_reader.claude_reader import ClaudeReader, reader_from_settings
from recipe_reader.reader import ConfigurationError, TechnicalError, UnconfiguredReader
from recipe_reader.settings import Settings
from tests.images import jpeg

API_KEY = "sk-ant-test-hemmelig-noegle"

BOLLER = {
    "titel": "Boller i karry",
    "portioner": 4,
    "forberedelse": None,
    "total": 75,
    "tags": [],
    "kilde": "Mormors kogebog",
    "ingredienser": [
        {"gruppe": "Til sovsen", "linjer": [{"maengde": 2, "enhed": "spsk", "navn": "karry"}, {"maengde": None, "enhed": None, "navn": "salt"}]}
    ],
    "trin": ["Lav sovsen."],
    "noter": None,
}


def message(text: str, stop_reason: str = "end_turn") -> dict[str, Any]:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 10},
    }


def reader_with(handler: Callable[[httpx2.Request], httpx2.Response]) -> ClaudeReader:
    client = anthropic.Anthropic(
        api_key=API_KEY,
        base_url="https://api.test",
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
        max_retries=0,
    )
    return ClaudeReader(client=client, model="claude-opus-5-5")


def answering(status: int, body: dict[str, Any] | str) -> Callable[[httpx2.Request], httpx2.Response]:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(status, json=body) if isinstance(body, dict) else httpx2.Response(status, text=body)

    return handler


def error(kind: str, text: str = "fejl") -> dict[str, Any]:
    return {"type": "error", "error": {"type": kind, "message": text}}


def test_the_images_and_the_contract_are_sent_and_drafts_come_back() -> None:
    requests: list[dict[str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(json.loads(request.content))
        return httpx2.Response(200, json=message(json.dumps({"opskrifter": [BOLLER, {**BOLLER, "titel": "Kartoffelsalat"}]})))

    images = [jpeg(color="red"), jpeg(color="blue")]
    drafts = reader_with(handler).read(images)

    assert [draft.titel for draft in drafts] == ["Boller i karry", "Kartoffelsalat"]
    assert drafts[0].model_dump() == BOLLER
    [body] = requests
    assert body["model"] == "claude-opus-5-5"
    content = body["messages"][0]["content"]
    sent = [block["source"]["data"] for block in content if block["type"] == "image"]
    assert sent == [base64.standard_b64encode(image).decode() for image in images]
    assert body["output_config"]["format"]["type"] == "json_schema"
    prompt = body["system"] if isinstance(body["system"], str) else " ".join(b["text"] for b in body["system"])
    for rule in ["dansk", "metriske", "null", "grupper", "ét udkast pr. opskrift", "fortsætter"]:
        assert rule in prompt, rule


def test_no_recipes_on_the_images_gives_an_empty_list() -> None:
    assert reader_with(answering(200, message('{"opskrifter": []}'))).read([jpeg()]) == []


@pytest.mark.parametrize(
    "text",
    [
        "ikke json",
        '{"opskrifter": [{"titel": "Halv',  # afbrudt svar
        '{"forkert": []}',
        json.dumps({"opskrifter": [{**BOLLER, "portioner": 0}]}),
        json.dumps({"opskrifter": [{**BOLLER, "ingredienser": [{"gruppe": None, "linjer": [{"maengde": -1, "enhed": "g", "navn": "smør"}]}]}]}),
    ],
    ids=["ikke json", "afbrudt", "forkert form", "0 portioner", "negativ mængde"],
)
def test_an_invalid_answer_is_a_technical_error_not_half_a_draft(text: str) -> None:
    with pytest.raises(TechnicalError) as raised:
        reader_with(answering(200, message(text))).read([jpeg()])

    assert not isinstance(raised.value, ConfigurationError)


@pytest.mark.parametrize("stop_reason", ["max_tokens", "refusal"])
def test_an_answer_that_was_cut_off_or_refused_is_a_technical_error(stop_reason: str) -> None:
    with pytest.raises(TechnicalError):
        reader_with(answering(200, message('{"opskrifter": []}', stop_reason))).read([jpeg()])


@pytest.mark.parametrize(
    ("status", "kind"),
    [(500, "api_error"), (529, "overloaded_error"), (503, "api_error"), (429, "rate_limit_error"), (400, "invalid_request_error")],
)
def test_server_errors_and_rate_limits_are_technical_errors(status: int, kind: str) -> None:
    with pytest.raises(TechnicalError) as raised:
        reader_with(answering(status, error(kind))).read([jpeg()])

    assert not isinstance(raised.value, ConfigurationError)


@pytest.mark.parametrize("exception", [httpx2.ConnectError("ingen forbindelse"), httpx2.ReadTimeout("timeout")])
def test_network_errors_and_timeouts_are_technical_errors(exception: Exception) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise exception

    with pytest.raises(TechnicalError) as raised:
        reader_with(handler).read([jpeg()])

    assert not isinstance(raised.value, ConfigurationError)


@pytest.mark.parametrize(("status", "kind"), [(401, "authentication_error"), (403, "permission_error"), (404, "not_found_error")])
def test_an_invalid_api_key_or_model_is_a_configuration_error(status: int, kind: str) -> None:
    with pytest.raises(ConfigurationError) as raised:
        reader_with(answering(status, error(kind))).read([jpeg()])

    assert "indstillinger" in str(raised.value)


def test_the_api_key_is_never_logged_or_shown(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    with pytest.raises(ConfigurationError) as raised:
        reader_with(answering(401, error("authentication_error", f"invalid x-api-key {API_KEY}"))).read([jpeg()])

    assert API_KEY not in str(raised.value)
    assert API_KEY not in caplog.text


def test_without_an_api_key_the_reader_is_unconfigured(tmp_path: Any) -> None:
    settings = Settings(library_dir=tmp_path, index_path=tmp_path / "index.sqlite", api_key=None)

    reader = reader_from_settings(settings)

    assert isinstance(reader, UnconfiguredReader)
    with pytest.raises(ConfigurationError):
        reader.read([jpeg()])


def test_with_an_api_key_the_model_comes_from_the_settings(tmp_path: Any) -> None:
    settings = Settings(library_dir=tmp_path, index_path=tmp_path / "index.sqlite", api_key=API_KEY, model="claude-sonnet-5-5")

    reader = reader_from_settings(settings)

    assert isinstance(reader, ClaudeReader)
    assert reader.model == "claude-sonnet-5-5"
    assert API_KEY not in repr(reader)
