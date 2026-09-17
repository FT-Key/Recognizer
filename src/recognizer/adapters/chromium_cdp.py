"""Implementacion de BrowserTabs via CDP sobre una instancia Chromium."""

import logging
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from recognizer.adapters.cdp_client import CdpClient, CdpTarget, CdpTransport
from recognizer.adapters.chromium import DetectedBrowser, resolve_profile_dir
from recognizer.core.domain.browser import TabKey, TabSpec
from recognizer.core.errors import ActionError

LOGGER = logging.getLogger("recognizer.cdp")

KEY_MAP: dict[str, tuple[str, str, int]] = {
    "ctrl": ("Control", "ControlLeft", 17),
    "shift": ("Shift", "ShiftLeft", 16),
    "alt": ("Alt", "AltLeft", 18),
    "enter": ("Enter", "Enter", 13),
    "escape": ("Escape", "Escape", 27),
    "space": (" ", "Space", 32),
    "tab": ("Tab", "Tab", 9),
    "backspace": ("Backspace", "Backspace", 8),
    "delete": ("Delete", "Delete", 46),
    "arrowup": ("ArrowUp", "ArrowUp", 38),
    "arrowdown": ("ArrowDown", "ArrowDown", 40),
    "arrowleft": ("ArrowLeft", "ArrowLeft", 37),
    "arrowright": ("ArrowRight", "ArrowRight", 39),
    "home": ("Home", "Home", 36),
    "end": ("End", "End", 35),
    "pageup": ("PageUp", "PageUp", 33),
    "pagedown": ("PageDown", "PageDown", 34),
}


def _map_key(key: str) -> tuple[str, str, int]:
    """Mapea una tecla a (key, code, virtualKeyCode)."""
    lower = key.lower()
    if lower in KEY_MAP:
        return KEY_MAP[lower]
    if len(key) == 1:
        vk = ord(key.upper())
        return (key, f"Key{key.upper()}", vk)
    return (key, key, 0)


class ChromiumCdpBrowser:
    """Implementa BrowserTabs via CDP sobre una instancia Chromium."""

    def __init__(
        self,
        *,
        tabs: Mapping[TabKey, TabSpec],
        detected: DetectedBrowser,
        profile_dir: Path,
        port: int = 9222,
        popen: Callable[..., object] | None = None,
        http: CdpTransport | None = None,
        ws: CdpTransport | None = None,
        client: CdpClient | None = None,
    ) -> None:
        self._tabs = tabs
        self._detected = detected
        self._profile_dir = self._resolve_profile_dir(profile_dir)
        self._port = port
        self._popen = popen or self._default_popen

        if client is not None:
            self._client: CdpClient = client
        else:
            from recognizer.adapters.cdp_client import UrllibCdpTransport, WebsocketCdpTransport

            http_transport = http or UrllibCdpTransport(port)
            ws_transport = ws or WebsocketCdpTransport(port)
            self._client = CdpClient(port=port, http=http_transport, ws=ws_transport)

    def ensure(self, *, tab: TabKey, url: str) -> None:
        """Abre la URL en la pestana registrada (o la crea) y la enfoca."""
        self._ensure_running()
        spec = self._tabs.get(tab)
        if spec is None:
            msg = f"Pestana no registrada: {tab}"
            raise ActionError(msg)

        target = self._find_target(spec.match)
        if target is not None:
            current_url = target.url
            if url not in current_url:
                self._client.navigate(target.id, url)
                self._client.activate_target(target.id)
            else:
                self._client.activate_target(target.id)
                with ExceptionHandler("Intentar play en video"):
                    self._client.evaluate(
                        target.id,
                        "document.querySelector('video')?.play()",
                        await_promise=False,
                    )
        else:
            target_id = self._client.create_target()
            self._client.navigate(target_id, url)
            self._client.activate_target(target_id)

    def seek_media(self, *, tab: TabKey, fraction: float) -> None:
        """Posiciona el <video> de la pestana en fraction (0.0..1.0)."""
        if not self._client.is_available():
            msg = "El navegador no esta disponible en CDP"
            raise ActionError(msg)

        spec = self._tabs.get(tab)
        if spec is None:
            msg = f"Pestana no registrada: {tab}"
            raise ActionError(msg)

        target = self._find_target(spec.match)
        if target is None:
            msg = f"No se encontro la pestana '{tab}' en el navegador"
            raise ActionError(msg)

        js = (
            "(() => {"
            "  const v = document.querySelector('video');"
            "  if (!v) return 'no-video';"
            "  if (Number.isFinite(v.duration) && v.duration > 0) {"
            f"    v.currentTime = v.duration * {fraction};"
            "  }"
            "  v.play();"
            "  return 'ok';"
            "})()"
        )
        result = self._client.evaluate(target.id, js)
        if result == "no-video":
            msg = f"No se encontro elemento <video> en la pestana '{tab}'"
            raise ActionError(msg)

    def press_keys(self, *, tab: TabKey, keys: Sequence[str]) -> None:
        """Envia teclas a la pestana via CDP Input.dispatchKeyEvent."""
        if not self._client.is_available():
            msg = "El navegador no esta disponible en CDP"
            raise ActionError(msg)

        spec = self._tabs.get(tab)
        if spec is None:
            msg = f"Pestana no registrada: {tab}"
            raise ActionError(msg)

        target = self._find_target(spec.match)
        if target is None:
            msg = f"No se encontro la pestana '{tab}' en el navegador"
            raise ActionError(msg)

        for key in keys:
            key_name, code, vk = _map_key(key)
            self._client.dispatch_key_down(target.id, key_name, code, vk)
            self._client.dispatch_key_up(target.id, key_name, code, vk)

    def _ensure_running(self) -> None:
        """Verifica si Chromium esta corriendo; si no, lo lanza."""
        if self._client.is_available():
            return

        self._ensure_default_profile()
        LOGGER.info("Lanzando Chromium en puerto %d", self._port)
        args = [
            self._detected.executable,
            f"--remote-debugging-port={self._port}",
            f"--user-data-dir={self._profile_dir}",
            "--profile-directory=Default",
            "--no-first-run",
            "--no-default-browser-check",
            "--remote-allow-origins=*",
            "--autoplay-policy=no-user-gesture-required",
            "--disable-sync",
            "--no-service-autorun",
        ]
        try:
            self._popen(args)
        except (OSError, ValueError) as exc:
            msg = "No se pudo lanzar el navegador Chromium"
            raise ActionError(msg) from exc

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            time.sleep(0.5)
            if self._client.is_available():
                LOGGER.info("Chromium listo en puerto %d", self._port)
                return

        msg = "Chromium no respondio en el tiempo esperado"
        raise ActionError(msg)

    def _ensure_default_profile(self) -> None:
        """Crea la estructura minima del perfil para evitar el selector de perfiles."""
        default_dir = self._profile_dir / "Default"
        default_dir.mkdir(parents=True, exist_ok=True)
        prefs_file = default_dir / "Preferences"
        if not prefs_file.exists():
            import json

            prefs_file.write_text(
                json.dumps({"profile": {"name": "Recognizer", "created_by_version": 1}}),
                encoding="utf-8",
            )
        local_state = self._profile_dir / "Local State"
        if not local_state.exists():
            import json

            local_state.write_text(
                json.dumps(
                    {
                        "profile": {
                            "profiles_order": ["Default"],
                            "last_used": "Default",
                        }
                    }
                ),
                encoding="utf-8",
            )

    def _find_target(self, match: str) -> CdpTarget | None:
        """Busca un target cuyo URL contiene match, priorizando el que reproduce."""
        targets = self._client.list_targets()
        playing: CdpTarget | None = None
        fallback: CdpTarget | None = None
        for target in targets:
            if match in target.url:
                if fallback is None:
                    fallback = target
                if playing is None:
                    with ExceptionHandler("Verificar estado de video"):
                        paused = self._client.evaluate(
                            target.id,
                            "document.querySelector('video')?.paused",
                            await_promise=False,
                        )
                        if paused is False:
                            playing = target
        return playing or fallback

    def _resolve_profile_dir(self, base_dir: Path) -> Path:
        """Resuelve el directorio del perfil (absoluto) con fallback a tmp.

        Chrome ignora silenciosamente ``--user-data-dir`` con rutas relativas,
        por lo que el perfil debe ser absoluto para que CDP funcione.
        """
        try:
            profile = resolve_profile_dir(self._detected, base_dir).resolve()
            profile.mkdir(parents=True, exist_ok=True)
            return profile
        except OSError:
            fallback = (
                Path(tempfile.gettempdir()) / "recognizer-browser" / self._detected.family.value
            ).resolve()
            fallback.mkdir(parents=True, exist_ok=True)
            LOGGER.warning(
                "No se pudo crear perfil en %s; usando %s",
                base_dir,
                fallback,
            )
            return fallback

    @staticmethod
    def _default_popen(argv: list[str]) -> object:
        """Lanza un proceso sin consola en Windows."""
        return subprocess.Popen(  # noqa: S603
            argv,
            shell=False,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )


class ExceptionHandler:
    """Suprime excepciones con logging (usado para operaciones best-effort)."""

    def __init__(self, description: str) -> None:
        self._description = description

    def __enter__(self) -> "ExceptionHandler":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> bool:
        if exc_type is not None:
            LOGGER.debug("%s: %s", self._description, exc_val)
        return True
