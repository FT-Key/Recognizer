"""Tests de la accion que ejecuta scripts locales delegando en el puerto."""

from recognizer.core.actions.script import ScriptAction
from recognizer.core.constants import (
    CONTEXT_ENV_CONFIDENCE,
    CONTEXT_ENV_GESTURE,
    CONTEXT_ENV_HANDEDNESS,
    CONTEXT_ENV_TIMESTAMP,
)
from recognizer.core.domain.action import (
    ActionContext,
    ScriptInterpreter,
    ScriptRequest,
)
from recognizer.core.domain.gesture import GESTURE_VICTORY
from recognizer.core.domain.hand import Handedness

GESTURE_CONFIDENCE = 0.75
TIMESTAMP = 12.5


class RecordingScriptRunner:
    """Doble de ScriptRunner que registra los requests recibidos."""

    def __init__(self) -> None:
        self.requests: list[ScriptRequest] = []

    def run(self, request: ScriptRequest) -> None:
        self.requests.append(request)


def _context() -> ActionContext:
    return ActionContext(
        gesture=GESTURE_VICTORY,
        confidence=GESTURE_CONFIDENCE,
        handedness=Handedness.RIGHT,
        timestamp=TIMESTAMP,
    )


def _request() -> ScriptRequest:
    return ScriptRequest(
        path="scripts/celebrate.py",
        args=("--loud",),
        interpreter=ScriptInterpreter.PYTHON,
        working_dir="scripts",
        blocking=True,
        timeout_seconds=3.0,
    )


def test_pass_context_injects_context_env_and_preserves_request() -> None:
    runner = RecordingScriptRunner()
    action = ScriptAction(request=_request(), runner=runner, pass_context=True)

    action.execute(_context())

    request = runner.requests[0]
    assert request.env == {
        CONTEXT_ENV_GESTURE: GESTURE_VICTORY.value,
        CONTEXT_ENV_HANDEDNESS: Handedness.RIGHT.value,
        CONTEXT_ENV_CONFIDENCE: str(GESTURE_CONFIDENCE),
        CONTEXT_ENV_TIMESTAMP: str(TIMESTAMP),
    }
    assert request.path == "scripts/celebrate.py"
    assert request.args == ("--loud",)
    assert request.interpreter is ScriptInterpreter.PYTHON
    assert request.working_dir == "scripts"
    assert request.blocking is True
    assert request.timeout_seconds == 3.0


def test_pass_context_false_forwards_env_none() -> None:
    runner = RecordingScriptRunner()
    action = ScriptAction(request=_request(), runner=runner, pass_context=False)

    action.execute(_context())

    assert runner.requests[0].env is None
