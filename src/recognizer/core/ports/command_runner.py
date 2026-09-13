"""Puerto de ejecucion de comandos locales."""

from collections.abc import Sequence
from typing import Protocol


class CommandRunner(Protocol):
    """Ejecuta un comando local a partir de su argv."""

    def run(self, argv: Sequence[str]) -> None:
        """Lanza el comando representado por argv."""
        ...
