"""Adaptador de ejecucion de comandos locales con subprocess."""

import subprocess
from collections.abc import Callable, Sequence

from recognizer.core.errors import ActionError
from recognizer.core.ports.command_runner import CommandRunner


def _default_popen(argv: Sequence[str]) -> object:
    # argv viene de config.yaml (confiable): shell desactivado a proposito.
    return subprocess.Popen(  # noqa: S603
        list(argv),
        shell=False,
        close_fds=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class SubprocessCommandRunner(CommandRunner):
    """Lanza comandos locales sin bloquear ni ensuciar la consola."""

    def __init__(self, *, popen: Callable[[Sequence[str]], object] | None = None) -> None:
        self._popen = popen or _default_popen

    def run(self, argv: Sequence[str]) -> None:
        """Lanza el comando representado por argv.

        Raises:
            ActionError: si el sistema no puede lanzar el comando.
        """
        try:
            self._popen(argv)
        except OSError as exc:
            program = argv[0] if argv else "desconocido"
            msg = f"No se pudo ejecutar el comando: {program}"
            raise ActionError(msg) from exc
