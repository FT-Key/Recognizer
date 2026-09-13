"""Accion que ejecuta un script local delegando en el ScriptRunner."""

from dataclasses import replace

from recognizer.core.constants import (
    CONTEXT_ENV_CONFIDENCE,
    CONTEXT_ENV_GESTURE,
    CONTEXT_ENV_HANDEDNESS,
    CONTEXT_ENV_TIMESTAMP,
)
from recognizer.core.domain.action import Action, ActionContext, ScriptRequest
from recognizer.core.ports.script_runner import ScriptRunner


class ScriptAction(Action):
    """Ejecuta un script local ante un gesto confirmado."""

    def __init__(
        self,
        *,
        request: ScriptRequest,
        runner: ScriptRunner,
        pass_context: bool,
    ) -> None:
        self._request = request
        self._runner = runner
        self._pass_context = pass_context

    def execute(self, context: ActionContext) -> None:
        """Construye el env de contexto si aplica y delega en el runner."""
        env = _context_env(context) if self._pass_context else None
        self._runner.run(replace(self._request, env=env))


def _context_env(context: ActionContext) -> dict[str, str]:
    return {
        CONTEXT_ENV_GESTURE: context.gesture.value,
        CONTEXT_ENV_HANDEDNESS: context.handedness.value,
        CONTEXT_ENV_CONFIDENCE: str(context.confidence),
        CONTEXT_ENV_TIMESTAMP: str(context.timestamp),
    }
