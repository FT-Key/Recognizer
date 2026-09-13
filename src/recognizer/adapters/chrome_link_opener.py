"""Adaptador que abre enlaces en Google Chrome en Windows."""

import os
import shutil
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

from recognizer.core.errors import ActionError
from recognizer.core.ports.link_opener import LinkOpener

CHROME_EXECUTABLE_NAME = "chrome.exe"
CHROME_COMMAND_NAME = "chrome"
PROGRAMFILES_ENV = "PROGRAMFILES"
PROGRAMFILES_X86_ENV = "PROGRAMFILES(X86)"
LOCALAPPDATA_ENV = "LOCALAPPDATA"
CHROME_RELATIVE_PATH = Path("Google") / "Chrome" / "Application" / CHROME_EXECUTABLE_NAME
CHROME_ENV_ROOTS = (PROGRAMFILES_ENV, PROGRAMFILES_X86_ENV, LOCALAPPDATA_ENV)


def _common_chrome_paths() -> tuple[Path, ...]:
    paths: list[Path] = []
    for env_var in CHROME_ENV_ROOTS:
        root = os.environ.get(env_var)
        if root:
            paths.append(Path(root) / CHROME_RELATIVE_PATH)
    return tuple(paths)


def _autodetect_chrome() -> str | None:
    found = shutil.which(CHROME_COMMAND_NAME)
    if found is not None:
        return found
    for candidate in _common_chrome_paths():
        if candidate.is_file():
            return str(candidate)
    return None


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
        executable = self._executable or _autodetect_chrome()
        if executable is None:
            msg = "No se encontro Chrome; define `browser` en la configuracion."
            raise ActionError(msg)
        try:
            self._popen((executable, url))
        except (OSError, ValueError) as exc:
            msg = f"No se pudo abrir el enlace: {url}"
            raise ActionError(msg) from exc
