"""Cliente CDP transportable para controlar Chromium."""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from contextlib import suppress
from dataclasses import dataclass
from typing import Protocol

from recognizer.core.errors import ActionError

LOGGER = logging.getLogger("recognizer.cdp")

type JsonValue = str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None


class CdpTransport(Protocol):
    """Transporte abstracto para comunicacion CDP."""

    def request_json(self, *, method: str, path: str, body: bytes | None = None) -> JsonValue:
        """Realiza una peticion HTTP y devuelve la respuesta JSON."""
        ...

    def command(
        self,
        *,
        ws_url: str,
        method: str,
        params: dict[str, JsonValue] | None = None,
    ) -> JsonValue:
        """Envia un comando CDP via WebSocket y devuelve la respuesta."""
        ...


class UrllibCdpTransport:
    """Transporte HTTP basado en urllib para CDP."""

    def __init__(self, port: int, *, timeout: float = 2.0) -> None:
        self._port = port
        self._timeout = timeout

    def request_json(self, *, method: str, path: str, body: bytes | None = None) -> JsonValue:
        """Realiza GET o PUT a http://127.0.0.1:{port}{path}."""
        url = f"http://127.0.0.1:{self._port}{path}"
        try:
            req = urllib.request.Request(url, method=method, data=body)
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # noqa: S310
                data = resp.read()
                result: JsonValue = json.loads(data)
                return result
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            msg = f"Error HTTP CDP ({method} {path}): {exc}"
            raise ActionError(msg) from exc
        except TimeoutError as exc:
            msg = f"Timeout CDP ({method} {path})"
            raise ActionError(msg) from exc
        except json.JSONDecodeError as exc:
            msg = f"Respuesta JSON invalida CDP ({method} {path})"
            raise ActionError(msg) from exc

    def command(
        self,
        *,
        ws_url: str,  # noqa: ARG002
        method: str,  # noqa: ARG002
        params: dict[str, JsonValue] | None = None,  # noqa: ARG002
    ) -> JsonValue:
        """No soportado en transporte HTTP; levanta ActionError."""
        msg = "UrllibCdpTransport no soporta comandos WebSocket"
        raise ActionError(msg)


class WebsocketCdpTransport:
    """Transporte WebSocket para comandos CDP."""

    def __init__(self, port: int, *, timeout: float = 3.0) -> None:
        self._port = port
        self._timeout = timeout

    def request_json(
        self,
        *,
        method: str,  # noqa: ARG002
        path: str,  # noqa: ARG002
        body: bytes | None = None,  # noqa: ARG002
    ) -> JsonValue:
        """No soportado en transporte WebSocket; levanta ActionError."""
        msg = "WebsocketCdpTransport no soporta peticiones HTTP"
        raise ActionError(msg)

    def command(
        self,
        *,
        ws_url: str,
        method: str,
        params: dict[str, JsonValue] | None = None,
    ) -> JsonValue:
        """Abre conexion WebSocket, envia comando CDP y espera respuesta."""
        try:
            import websocket
        except ImportError as exc:
            msg = (
                "Se requiere websocket-client para controlar el navegador. "
                "Instala con: uv add websocket-client"
            )
            raise ActionError(msg) from exc

        ws = None
        try:
            ws = websocket.create_connection(
                ws_url,
                timeout=self._timeout,
                suppress_origin=True,
            )
            command_id = 1
            payload = json.dumps(
                {
                    "id": command_id,
                    "method": method,
                    "params": params or {},
                }
            )
            ws.send(payload)
            while True:
                raw = ws.recv()
                msg_data: dict[str, JsonValue] = json.loads(raw)
                if msg_data.get("id") == command_id:
                    if "error" in msg_data:
                        error = msg_data["error"]
                        msg = f"Error CDP {method}: {error}"
                        raise ActionError(msg)
                    return msg_data.get("result")
        except ActionError:
            raise
        except Exception as exc:
            msg = f"Error WebSocket CDP ({method}): {exc}"
            raise ActionError(msg) from exc
        finally:
            if ws is not None:
                with suppress(Exception):
                    ws.close()


@dataclass(frozen=True, slots=True)
class CdpTarget:
    """Target (pestana/pagina) detectado via CDP."""

    id: str
    url: str
    title: str
    type: str
    ws_url: str


class CdpClient:
    """Cliente CDP que combina HTTP y WebSocket para controlar Chromium."""

    def __init__(
        self,
        *,
        port: int,
        http: CdpTransport,
        ws: CdpTransport,
    ) -> None:
        self._port = port
        self._http = http
        self._ws = ws

    def is_available(self) -> bool:
        """Verifica si el navegador esta disponible en el puerto CDP."""
        try:
            result = self._http.request_json(method="GET", path="/json/version")
            return isinstance(result, dict) and "Browser" in result
        except ActionError:
            return False

    def list_targets(self) -> tuple[CdpTarget, ...]:
        """Lista los targets (pestanas) abiertos."""
        result = self._http.request_json(method="GET", path="/json/list")
        if not isinstance(result, list):
            return ()
        targets: list[CdpTarget] = []
        for item in result:
            if not isinstance(item, dict):
                continue
            target_type = item.get("type", "")
            if target_type != "page":
                continue
            targets.append(
                CdpTarget(
                    id=str(item.get("id", "")),
                    url=str(item.get("url", "")),
                    title=str(item.get("title", "")),
                    type=str(target_type),
                    ws_url=str(item.get("webSocketDebuggerUrl", "")),
                )
            )
        return tuple(targets)

    def create_target(self, url: str) -> str:
        """Crea un nuevo target con la URL indicada y devuelve su ID."""
        encoded_url = urllib.parse.quote(url, safe="")
        result = self._http.request_json(
            method="PUT",
            path=f"/json/new?url={encoded_url}",
        )
        if not isinstance(result, dict):
            msg = "Respuesta invalida al crear target"
            raise ActionError(msg)
        target_id = result.get("id")
        if not isinstance(target_id, str):
            msg = "No se pudo obtener el ID del nuevo target"
            raise ActionError(msg)
        return target_id

    def activate_target(self, target_id: str) -> None:
        """Activa (enfoca) un target existente."""
        self._http.request_json(method="PUT", path=f"/json/activate/{target_id}")

    def navigate(self, target_id: str, url: str) -> None:
        """Navega un target a la URL indicada via Page.navigate."""
        target = self._find_target_by_id(target_id)
        self._ws.command(
            ws_url=target.ws_url,
            method="Page.navigate",
            params={"url": url},
        )

    def evaluate(
        self,
        target_id: str,
        expression: str,
        *,
        await_promise: bool = True,
    ) -> JsonValue:
        """Evalua una expresion JavaScript en el target."""
        target = self._find_target_by_id(target_id)
        result = self._ws.command(
            ws_url=target.ws_url,
            method="Runtime.evaluate",
            params={
                "expression": expression,
                "awaitPromise": await_promise,
            },
        )
        if isinstance(result, dict) and "result" in result:
            inner = result["result"]
            if isinstance(inner, dict):
                return inner.get("value")
        return None

    def dispatch_key_down(
        self,
        target_id: str,
        key: str,
        code: str,
        windows_virtual_key_code: int,
        modifiers: int = 0,
        text: str = "",
    ) -> None:
        """Envia un evento key down via CDP Input.dispatchKeyEvent."""
        target = self._find_target_by_id(target_id)
        self._ws.command(
            ws_url=target.ws_url,
            method="Input.dispatchKeyEvent",
            params={
                "type": "keyDown",
                "key": key,
                "code": code,
                "windowsVirtualKeyCode": windows_virtual_key_code,
                "modifiers": modifiers,
                "text": text,
            },
        )

    def dispatch_key_up(
        self,
        target_id: str,
        key: str,
        code: str,
        windows_virtual_key_code: int,
        modifiers: int = 0,
    ) -> None:
        """Envia un evento key up via CDP Input.dispatchKeyEvent."""
        target = self._find_target_by_id(target_id)
        self._ws.command(
            ws_url=target.ws_url,
            method="Input.dispatchKeyEvent",
            params={
                "type": "keyUp",
                "key": key,
                "code": code,
                "windowsVirtualKeyCode": windows_virtual_key_code,
                "modifiers": modifiers,
            },
        )

    def _find_target_by_id(self, target_id: str) -> CdpTarget:
        """Busca un target por ID en la lista de targets."""
        for target in self.list_targets():
            if target.id == target_id:
                return target
        msg = f"Target no encontrado: {target_id}"
        raise ActionError(msg)
