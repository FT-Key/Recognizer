"""Tests del clicker del puntero suscrito a PointerClicked."""

import logging

import pytest

from recognizer.core.actions.decorators import ActionGate
from recognizer.core.constants import POINTER_LOGGER_NAME
from recognizer.core.domain.events import (
    DomainEvent,
    GestureDetected,
    HandsDetected,
    PointerClicked,
    PointerMoved,
    PointerReleased,
)
from recognizer.core.domain.gesture import GESTURE_VICTORY
from recognizer.core.domain.hand import Handedness
from recognizer.core.errors import ActionError
from recognizer.core.pointer.clicker import PointerClicker

EVENT_TIMESTAMP = 1.0
GESTURE_CONFIDENCE = 0.8


class RecordingMouseController:
    """Doble de MouseController que registra los clicks recibidos."""

    def __init__(self) -> None:
        self.clicks = 0
        self.scrolls: list[tuple[int, int]] = []

    def move_to(self, *, x: float, y: float) -> None:
        pass

    def click(self) -> None:
        self.clicks += 1

    def scroll_by(self, *, dx: int, dy: int) -> None:
        self.scrolls.append((dx, dy))


class FailingMouseController:
    """Doble que siempre falla al hacer click con ActionError."""

    def move_to(self, *, x: float, y: float) -> None:
        pass

    def click(self) -> None:
        msg = "sin mouse"
        raise ActionError(msg)

    def scroll_by(self, *, dx: int, dy: int) -> None:
        del dx, dy
        msg = "sin mouse"
        raise ActionError(msg)


def _event() -> PointerClicked:
    return PointerClicked(timestamp=EVENT_TIMESTAMP)


def test_pointer_clicked_clicks_controller() -> None:
    controller = RecordingMouseController()
    clicker = PointerClicker(controller=controller)

    clicker.handle(_event())

    assert controller.clicks == 1


def test_disabled_gate_blocks_and_reenabling_allows() -> None:
    controller = RecordingMouseController()
    gate = ActionGate()
    clicker = PointerClicker(controller=controller, gate=gate)

    assert gate.toggle() is False
    clicker.handle(_event())
    assert controller.clicks == 0

    assert gate.toggle() is True
    clicker.handle(_event())
    assert controller.clicks == 1


def test_action_error_is_logged_and_not_propagated(
    caplog: pytest.LogCaptureFixture,
) -> None:
    clicker = PointerClicker(controller=FailingMouseController())

    with caplog.at_level(logging.WARNING, logger=POINTER_LOGGER_NAME):
        clicker.handle(_event())

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == logging.WARNING
    assert record.name == POINTER_LOGGER_NAME
    assert "click" in record.getMessage().lower()


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
        PointerMoved(timestamp=EVENT_TIMESTAMP, x=0.5, y=0.5),
        PointerReleased(timestamp=EVENT_TIMESTAMP),
    ],
)
def test_other_events_are_ignored(event: DomainEvent) -> None:
    controller = RecordingMouseController()
    clicker = PointerClicker(controller=controller)

    clicker.handle(event)

    assert controller.clicks == 0
