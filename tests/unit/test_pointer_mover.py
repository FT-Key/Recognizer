"""Tests del mover del puntero suscrito a PointerMoved."""

import logging

import pytest

from recognizer.core.actions.decorators import ActionGate
from recognizer.core.constants import POINTER_LOGGER_NAME
from recognizer.core.domain.events import (
    DomainEvent,
    GestureDetected,
    HandsDetected,
    PointerMoved,
)
from recognizer.core.domain.gesture import GESTURE_VICTORY
from recognizer.core.domain.hand import Handedness
from recognizer.core.errors import ActionError
from recognizer.core.pointer.mover import PointerMover

EVENT_TIMESTAMP = 1.0
POINTER_X = 0.25
POINTER_Y = 0.75
GESTURE_CONFIDENCE = 0.8


class RecordingMouseController:
    """Doble de MouseController que registra las posiciones recibidas."""

    def __init__(self) -> None:
        self.moves: list[tuple[float, float]] = []

    def move_to(self, *, x: float, y: float) -> None:
        self.moves.append((x, y))


class FailingMouseController:
    """Doble que siempre falla al mover con ActionError."""

    def move_to(self, *, x: float, y: float) -> None:
        del x, y
        msg = "sin mouse"
        raise ActionError(msg)


def _event(*, x: float = POINTER_X, y: float = POINTER_Y) -> PointerMoved:
    return PointerMoved(timestamp=EVENT_TIMESTAMP, x=x, y=y)


def test_pointer_moved_moves_controller_without_gate() -> None:
    controller = RecordingMouseController()
    mover = PointerMover(controller=controller)

    mover.handle(_event())

    assert controller.moves == [(POINTER_X, POINTER_Y)]


def test_disabled_gate_blocks_and_reenabling_allows() -> None:
    controller = RecordingMouseController()
    gate = ActionGate()
    mover = PointerMover(controller=controller, gate=gate)

    assert gate.toggle() is False
    mover.handle(_event())
    assert controller.moves == []

    assert gate.toggle() is True
    mover.handle(_event())
    assert controller.moves == [(POINTER_X, POINTER_Y)]


def test_action_error_is_logged_and_not_propagated(
    caplog: pytest.LogCaptureFixture,
) -> None:
    mover = PointerMover(controller=FailingMouseController())

    with caplog.at_level(logging.WARNING, logger=POINTER_LOGGER_NAME):
        mover.handle(_event())

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == logging.WARNING
    assert record.name == POINTER_LOGGER_NAME
    assert "puntero" in record.getMessage().lower()


@pytest.mark.parametrize(
    "event",
    [
        HandsDetected(timestamp=EVENT_TIMESTAMP, hands=()),
        GestureDetected(
            timestamp=EVENT_TIMESTAMP,
            gesture=GESTURE_VICTORY,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.RIGHT,
        ),
    ],
)
def test_other_events_are_ignored(event: DomainEvent) -> None:
    controller = RecordingMouseController()
    mover = PointerMover(controller=controller)

    mover.handle(event)

    assert controller.moves == []
