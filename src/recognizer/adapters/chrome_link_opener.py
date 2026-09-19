"""Adaptador que abre enlaces en el navegador Chromium en Windows."""

import subprocess
from collections.abc import Callable, Sequence

from recognizer.adapters.chromium import autodetect_browser
from recognizer.core.errors import ActionError
from recognizer.core.ports.link_opener import LinkOpener


def autodetect_chrome() -> str | None:
    """Detecta un navegador Chromium en el sistema y devuelve su ejecutable."""
    detected = autodetect_browser()
    if detected is None:
        return None
    return detected.executable


def _default_popen(argv: Sequence[str]) -> object:
    # argv viene de config.yaml (confiable): shell desactivado a proposito.
    return subprocess.Popen(  # noqa: S603
        list(argv),
        shell=False,
        close_fds=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class ChromeLinkOpener(LinkOpener):
    """Abre cada URL en Chrome lanzando ``chrome.exe <url>``.

    Si Chrome ya se esta ejecutando, el nuevo proceso delega la URL en la
    instancia existente y abre una pestana; si no, lanza Chrome y navega a la
    URL. Por eso no hace falta detectar el proceso en ejecucion.
    """

    def __init__(
        self,
        *,
        executable: str | None = None,
        popen: Callable[..., object] | None = None,
    ) -> None:
        self._executable = executable
        self._popen = popen or _default_popen

    def open(self, url: str) -> None:
        """Abre url en Chrome.

        Raises:
            ActionError: si no se encuentra Chrome o si el sistema no puede
                lanzarlo.
        """
        executable = self._executable or autodetect_chrome()
        if executable is None:
            msg = "No se encontro Chrome; define `browser` en la configuracion."
            raise ActionError(msg)
        try:
            self._popen((executable, url))
        except (OSError, ValueError) as exc:
            msg = f"No se pudo abrir el enlace: {url}"
            raise ActionError(msg) from exc
