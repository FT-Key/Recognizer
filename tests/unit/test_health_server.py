"""Tests del servidor de salud local (adaptador), sin hardware real."""

import json
from collections.abc import Iterator
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from recognizer.adapters.health_server import HEALTH_PATH, HealthServer

APP_NAME = "recognizer"
APP_VERSION = "0.1.0"
HTTP_OK = 200
HTTP_NOT_FOUND = 404
HTTP_NO_CONTENT = 204
TIMEOUT_SECONDS = 2.0
UNKNOWN_PATH = "/nope"


@pytest.fixture
def server() -> Iterator[HealthServer]:
    instance = HealthServer(port=0, app_name=APP_NAME, version=APP_VERSION)
    instance.start()
    try:
        yield instance
    finally:
        instance.stop()


def _url(server: HealthServer, path: str) -> str:
    return f"http://127.0.0.1:{server.port}{path}"


def test_health_endpoint_returns_payload(server: HealthServer) -> None:
    with urlopen(_url(server, HEALTH_PATH), timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
        assert response.status == HTTP_OK
        payload = json.loads(response.read().decode("utf-8"))

    assert payload["app"] == APP_NAME
    assert payload["version"] == APP_VERSION
    assert payload["status"] == "ok"


def test_health_endpoint_sends_cors_headers(server: HealthServer) -> None:
    with urlopen(_url(server, HEALTH_PATH), timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
        assert response.headers["Access-Control-Allow-Origin"] == "*"
        assert response.headers["Access-Control-Allow-Private-Network"] == "true"


def test_options_preflight_returns_no_content(server: HealthServer) -> None:
    request = Request(_url(server, HEALTH_PATH), method="OPTIONS")  # noqa: S310
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
        assert response.status == HTTP_NO_CONTENT


def test_unknown_path_returns_404(server: HealthServer) -> None:
    with pytest.raises(HTTPError) as excinfo:
        urlopen(_url(server, UNKNOWN_PATH), timeout=TIMEOUT_SECONDS)  # noqa: S310

    assert excinfo.value.code == HTTP_NOT_FOUND


def test_port_zero_is_resolved(server: HealthServer) -> None:
    assert server.port > 0


def test_start_is_idempotent(server: HealthServer) -> None:
    assert server.start() == server.port


def test_stop_is_idempotent(server: HealthServer) -> None:
    server.stop()
    server.stop()
