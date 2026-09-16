"""Servidor HTTP local minimo para que la web detecte la app de escritorio.

Es infraestructura (adaptador): abre un puerto en ``127.0.0.1`` y responde
``GET /health`` con informacion de la app. La version web lo sondea desde el
navegador para mostrar el banner "abrir app" en vez de "descargar app".

Seguridad: solo escucha en loopback y expone un unico endpoint de solo lectura.
"""

import json
import logging
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOGGER = logging.getLogger("recognizer.health")

HEALTH_PATH = "/health"
DEFAULT_HOST = "127.0.0.1"
JSON_CONTENT_TYPE = "application/json"
CORS_ALLOW_ORIGIN = "*"
CORS_ALLOW_METHODS = "GET, OPTIONS"
CORS_ALLOW_HEADERS = "Content-Type"
PRIVATE_NETWORK_HEADER = "Access-Control-Allow-Private-Network"
SERVER_NAME = "RecognizerHealth/1.0"
NOT_FOUND_BODY = b'{"error":"not found"}'
API_VERSION = 1


class _HealthHandler(BaseHTTPRequestHandler):
    """Responde /health con CORS y cabecera de Private Network Access."""

    server_version = SERVER_NAME
    payload: bytes = b"{}"

    def do_GET(self) -> None:
        """Devuelve el payload en /health o 404 en cualquier otra ruta."""
        path = self.path.split("?", 1)[0]
        if path != HEALTH_PATH:
            self._send(status=HTTPStatus.NOT_FOUND, body=NOT_FOUND_BODY)
            return
        self._send(status=HTTPStatus.OK, body=self.payload)

    def do_OPTIONS(self) -> None:
        """Responde al preflight CORS (incluido el de Private Network Access)."""
        self._send(status=HTTPStatus.NO_CONTENT, body=b"")

    def _send(self, *, status: HTTPStatus, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", JSON_CONTENT_TYPE)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", CORS_ALLOW_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", CORS_ALLOW_METHODS)
        self.send_header("Access-Control-Allow-Headers", CORS_ALLOW_HEADERS)
        self.send_header(PRIVATE_NETWORK_HEADER, "true")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        """Silencia el log por defecto; en DEBUG lo redirige a logging."""
        LOGGER.debug("health: " + fmt, *args)


def _make_handler(payload: bytes) -> type[BaseHTTPRequestHandler]:
    """Crea un handler ligado al payload de esta instancia."""

    class _BoundHealthHandler(_HealthHandler):
        pass

    _BoundHealthHandler.payload = payload
    return _BoundHealthHandler


class HealthServer:
    """Servidor de salud local en un hilo daemon.

    Ejemplo:
        server = HealthServer(port=8765, app_name="recognizer", version="0.1.0")
        server.start()
        ...
        server.stop()
    """

    def __init__(
        self,
        *,
        port: int,
        app_name: str,
        version: str,
        host: str = DEFAULT_HOST,
    ) -> None:
        self._requested_port = port
        self._host = host
        payload = {
            "app": app_name,
            "version": version,
            "status": "ok",
            "api": API_VERSION,
        }
        self._payload = json.dumps(payload).encode("utf-8")
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        """Puerto efectivo (util si se pidio el puerto 0)."""
        if self._server is None:
            return self._requested_port
        return int(self._server.server_address[1])

    def start(self) -> int:
        """Arranca el servidor en un hilo daemon y devuelve el puerto efectivo.

        Raises:
            OSError: si el puerto no puede abrirse (p. ej. ya esta en uso).
        """
        if self._server is not None:
            return self.port

        server = ThreadingHTTPServer(
            (self._host, self._requested_port),
            _make_handler(self._payload),
        )
        server.daemon_threads = True
        thread = threading.Thread(
            target=server.serve_forever, name="recognizer-health", daemon=True
        )
        thread.start()

        self._server = server
        self._thread = thread
        LOGGER.info("Servidor de salud en http://%s:%d%s", self._host, self.port, HEALTH_PATH)
        return self.port

    def stop(self) -> None:
        """Detiene el servidor; es idempotente."""
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None
        self._thread = None
