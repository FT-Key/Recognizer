"""Puerto de ejecucion de scripts locales."""

from typing import Protocol

from recognizer.core.domain.action import ScriptRequest


class ScriptRunner(Protocol):
    """Ejecuta un script local descrito por un ScriptRequest."""

    def run(self, request: ScriptRequest) -> None:
        """Ejecuta el script descrito por request."""
        ...
