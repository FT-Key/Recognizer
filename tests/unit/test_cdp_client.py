"""Tests del cliente CDP con transportes doblados."""

from __future__ import annotations

from typing import Any

import pytest

from recognizer.adapters.cdp_client import CdpClient, CdpTarget, JsonValue
from recognizer.core.errors import ActionError


class FakeCdpTransport:
    """Transporte doble que simula respuestas HTTP y comandos WebSocket."""

    def __init__(
        self,
        *,
        http_responses: dict[str, Any] | None = None,
        ws_response: Any = None,
        error_on: set[str] | None = None,
    ) -> None:
        self._http_responses = http_responses or {}
        self._ws_response = ws_response
        self._error_on = error_on or set()
        self.ws_calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def request_json(
        self,
        *,
        method: str,
        path: str,
        body: bytes | None = None,  # noqa: ARG002
    ) -> JsonValue:
        key = f"{method} {path}"
        if key in self._error_on:
            msg = f"Error HTTP simulado: {key}"
            raise ActionError(msg)
        return self._http_responses.get(path)

    def command(
        self,
        *,
        ws_url: str,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> JsonValue:
        self.ws_calls.append((ws_url, method, params))
        if method in self._error_on:
            msg = f"Error WS simulado: {method}"
            raise ActionError(msg)
        return self._ws_response  # type: ignore[no-any-return]


def _page_dict(
    target_id: str = "t1",
    url: str = "https://x.com",
    title: str = "T",
    ws_url: str = "ws://x",
) -> dict[str, Any]:
    return {
        "id": target_id,
        "url": url,
        "title": title,
        "type": "page",
        "webSocketDebuggerUrl": ws_url,
    }


def _target(
    target_id: str = "t1",
    url: str = "https://example.com",
    ws_url: str = "ws://127.0.0.1:9222/devtools/page/t1",
) -> CdpTarget:
    return CdpTarget(
        id=target_id,
        url=url,
        title="Test Page",
        type="page",
        ws_url=ws_url,
    )


def _make_client(
    http: FakeCdpTransport | None = None,
    ws: FakeCdpTransport | None = None,
) -> tuple[CdpClient, FakeCdpTransport, FakeCdpTransport]:
    http = http or FakeCdpTransport()
    ws = ws or FakeCdpTransport()
    return CdpClient(port=9222, http=http, ws=ws), http, ws


def _http_with_pages(*pages: dict[str, Any]) -> FakeCdpTransport:
    return FakeCdpTransport(http_responses={"/json/list": list(pages)})


class TestIsAvailable:
    def test_returns_true_on_valid_response(self) -> None:
        resp = {"Browser": "Chrome/136.0"}
        http = FakeCdpTransport(http_responses={"/json/version": resp})
        client, _, _ = _make_client(http=http)
        assert client.is_available() is True

    def test_returns_false_on_http_error(self) -> None:
        http = FakeCdpTransport(error_on={"GET /json/version"})
        client, _, _ = _make_client(http=http)
        assert client.is_available() is False

    def test_returns_false_on_wrong_shape(self) -> None:
        http = FakeCdpTransport(http_responses={"/json/version": "not-a-dict"})
        client, _, _ = _make_client(http=http)
        assert client.is_available() is False

    def test_returns_false_on_missing_browser_key(self) -> None:
        http = FakeCdpTransport(http_responses={"/json/version": {"Other": "val"}})
        client, _, _ = _make_client(http=http)
        assert client.is_available() is False


class TestListTargets:
    def test_filters_pages_only(self) -> None:
        page_a = _page_dict("t1", "https://a.com", "A", "ws://x")
        iframe = {
            "id": "t2",
            "url": "https://b.com",
            "title": "B",
            "type": "iframe",
            "webSocketDebuggerUrl": "ws://y",
        }
        page_c = _page_dict("t3", "https://c.com", "C", "ws://z")
        http = FakeCdpTransport(
            http_responses={"/json/list": [page_a, iframe, page_c]},
        )
        client, _, _ = _make_client(http=http)
        targets = client.list_targets()
        assert len(targets) == 2
        assert targets[0].id == "t1"
        assert targets[1].id == "t3"

    def test_excludes_service_workers(self) -> None:
        sw = {
            "id": "t1",
            "url": "https://a.com",
            "title": "A",
            "type": "service_worker",
            "webSocketDebuggerUrl": "ws://x",
        }
        http = FakeCdpTransport(http_responses={"/json/list": [sw]})
        client, _, _ = _make_client(http=http)
        assert client.list_targets() == ()

    def test_returns_empty_on_non_list_response(self) -> None:
        http = FakeCdpTransport(http_responses={"/json/list": "bad"})
        client, _, _ = _make_client(http=http)
        assert client.list_targets() == ()

    def test_skips_non_dict_items(self) -> None:
        page = _page_dict("t1", "https://a.com", "A", "ws://x")
        http = FakeCdpTransport(
            http_responses={"/json/list": ["bad", 42, page]},
        )
        client, _, _ = _make_client(http=http)
        targets = client.list_targets()
        assert len(targets) == 1


class TestCreateTarget:
    def test_calls_put_and_extracts_id(self) -> None:
        path = "/json/new?url=https%3A%2F%2Fexample.com"
        http = FakeCdpTransport(http_responses={path: {"id": "new-123"}})
        client, _, _ = _make_client(http=http)
        target_id = client.create_target("https://example.com")
        assert target_id == "new-123"

    def test_raises_on_invalid_response(self) -> None:
        path = "/json/new?url=https%3A%2F%2Fexample.com"
        http = FakeCdpTransport(http_responses={path: "bad"})
        client, _, _ = _make_client(http=http)
        with pytest.raises(ActionError, match="Respuesta invalida"):
            client.create_target("https://example.com")

    def test_raises_on_missing_id(self) -> None:
        path = "/json/new?url=https%3A%2F%2Fexample.com"
        http = FakeCdpTransport(http_responses={path: {"other": "val"}})
        client, _, _ = _make_client(http=http)
        with pytest.raises(ActionError, match="No se pudo obtener el ID"):
            client.create_target("https://example.com")


class TestActivateTarget:
    def test_calls_put_activate(self) -> None:
        http = FakeCdpTransport(http_responses={"/json/activate/t1": {}})
        client, _, _ = _make_client(http=http)
        client.activate_target("t1")


class TestNavigate:
    def test_sends_page_navigate(self) -> None:
        http = _http_with_pages(_page_dict("t1", "https://old.com"))
        ws = FakeCdpTransport(ws_response={"result": {}})
        client, _, _ = _make_client(http=http, ws=ws)
        client.navigate("t1", "https://new.com")
        assert len(ws.ws_calls) == 1
        _ws_url, method, params = ws.ws_calls[0]
        assert method == "Page.navigate"
        assert params is not None
        assert params["url"] == "https://new.com"


class TestEvaluate:
    def test_sends_runtime_evaluate(self) -> None:
        http = _http_with_pages(_page_dict())
        ws = FakeCdpTransport(ws_response={"result": {"value": 42}})
        client, _, _ = _make_client(http=http, ws=ws)
        result = client.evaluate("t1", "1 + 1")
        assert result == 42
        assert ws.ws_calls[0][1] == "Runtime.evaluate"
        params = ws.ws_calls[0][2]
        assert params is not None
        assert params["expression"] == "1 + 1"
        assert params["awaitPromise"] is True

    def test_returns_none_on_missing_value(self) -> None:
        http = _http_with_pages(_page_dict())
        ws = FakeCdpTransport(ws_response={"result": {}})
        client, _, _ = _make_client(http=http, ws=ws)
        assert client.evaluate("t1", "void 0") is None

    def test_evaluate_with_await_false(self) -> None:
        http = _http_with_pages(_page_dict())
        ws = FakeCdpTransport(ws_response={"result": {"value": True}})
        client, _, _ = _make_client(http=http, ws=ws)
        client.evaluate("t1", "expr", await_promise=False)
        params = ws.ws_calls[0][2]
        assert params is not None
        assert params["awaitPromise"] is False


class TestDispatchKeyEvent:
    def test_dispatch_key_down_sends_correct_params(self) -> None:
        http = _http_with_pages(_page_dict())
        ws = FakeCdpTransport(ws_response={"result": {}})
        client, _, _ = _make_client(http=http, ws=ws)
        client.dispatch_key_down(
            "t1",
            "a",
            "KeyA",
            65,
            modifiers=0,
            text="a",
        )
        assert ws.ws_calls[0][1] == "Input.dispatchKeyEvent"
        params = ws.ws_calls[0][2]
        assert params is not None
        assert params["type"] == "keyDown"
        assert params["key"] == "a"
        assert params["code"] == "KeyA"
        assert params["windowsVirtualKeyCode"] == 65
        assert params["modifiers"] == 0
        assert params["text"] == "a"

    def test_dispatch_key_up_sends_correct_params(self) -> None:
        http = _http_with_pages(_page_dict())
        ws = FakeCdpTransport(ws_response={"result": {}})
        client, _, _ = _make_client(http=http, ws=ws)
        client.dispatch_key_up("t1", "Enter", "Enter", 13, modifiers=0)
        params = ws.ws_calls[0][2]
        assert params is not None
        assert params["type"] == "keyUp"
        assert params["key"] == "Enter"

    def test_command_timeout_raises_action_error(self) -> None:
        http = _http_with_pages(_page_dict())
        ws = FakeCdpTransport(error_on={"Page.navigate"})
        client, _, _ = _make_client(http=http, ws=ws)
        with pytest.raises(ActionError, match="Error WS simulado"):
            client.navigate("t1", "https://y.com")


class TestFindTargetById:
    def test_raises_on_missing_target(self) -> None:
        http = FakeCdpTransport(http_responses={"/json/list": []})
        ws = FakeCdpTransport()
        client, _, _ = _make_client(http=http, ws=ws)
        with pytest.raises(ActionError, match="Target no encontrado"):
            client.navigate("nonexistent", "https://y.com")
