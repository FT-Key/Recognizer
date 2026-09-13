"""Tests del despachador de gestos confirmados a acciones locales."""

import logging

import pytest

from recognizer.core.actions.dispatcher import GestureActionDispatcher
from recognizer.core.constants import ACTION_LOGGER_NAME
from recognizer.core.domain.action import ActionContext
from recognizer.core.domain.events import (
    DomainEvent,
    GestureDetected,
    GestureReleased,
    HandsDetected,
)
from recognizer.core.domain.gesture import (
    GESTURE_NONE,
    GESTURE_OPEN_PALM,
    GESTURE_VICTORY,
    GestureId,
)
from recognizer.core.domain.hand import Handedness
from recognizer.core.errors import ActionError

GESTURE_CONFIDENCE = 0.8
TIMESTAMP = 1.0


class RecordingAction:
    """Doble de Action que acumula los contextos ejecutados."""

    def __init__(self) -> None:
        self.contexts: list[ActionContext] = []

    def execute(self, context: ActionContext) -> None:
        self.contexts.append(context)


class FailingAction:
    """Doble de Action que siempre falla con ActionError."""

    def execute(self, context: ActionContext) -> None:
        del context
        msg = "fallo simulado"
        raise ActionError(msg)


def _detected(
    gesture: GestureId = GESTURE_VICTORY,
    *,
    confidence: float = GESTURE_CONFIDENCE,
) -> GestureDetected:
    return GestureDetected(
        timestamp=TIMESTAMP,
        gesture=gesture,
        confidence=confidence,
        handedness=Handedness.RIGHT,
    )


def test_mapped_gesture_executes_with_context() -> None:
    action = RecordingAction()
    dispatcher = GestureActionDispatcher(actions={GESTURE_VICTORY: action})

    dispatcher.handle(_detected())

    assert action.contexts == [
        ActionContext(
            gesture=GESTURE_VICTORY,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.RIGHT,
            timestamp=TIMESTAMP,
        )
    ]


def test_unmapped_gesture_does_not_raise_with_default_fallback() -> None:
    dispatcher = GestureActionDispatcher(actions={GESTURE_VICTORY: RecordingAction()})

    dispatcher.handle(_detected(GESTURE_OPEN_PALM))


def test_unmapped_gesture_uses_injected_fallback() -> None:
    fallback = RecordingAction()
    dispatcher = GestureActionDispatcher(actions={}, fallback=fallback)

    dispatcher.handle(_detected(GESTURE_OPEN_PALM))

    assert len(fallback.contexts) == 1
    assert fallback.contexts[0].gesture is GESTURE_OPEN_PALM


def test_none_gesture_is_ignored() -> None:
    fallback = RecordingAction()
    dispatcher = GestureActionDispatcher(actions={}, fallback=fallback)

    dispatcher.handle(_detected(GESTURE_NONE))

    assert fallback.contexts == []


@pytest.mark.parametrize(
    "event",
    [
        GestureReleased(
            timestamp=TIMESTAMP,
            gesture=GESTURE_VICTORY,
            handedness=Handedness.RIGHT,
        ),
        HandsDetected(timestamp=TIMESTAMP, hands=()),
    ],
)
def test_other_events_are_ignored(event: DomainEvent) -> None:
    fallback = RecordingAction()
    dispatcher = GestureActionDispatcher(actions={}, fallback=fallback)

    dispatcher.handle(event)

    assert fallback.contexts == []


def test_action_error_is_logged_as_warning_and_not_propagated(
    caplog: pytest.LogCaptureFixture,
) -> None:
    dispatcher = GestureActionDispatcher(actions={GESTURE_VICTORY: FailingAction()})

    with caplog.at_level(logging.WARNING, logger=ACTION_LOGGER_NAME):
        dispatcher.handle(_detected())

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == logging.WARNING
    assert record.name == ACTION_LOGGER_NAME
    assert GESTURE_VICTORY.value in record.getMessage()
