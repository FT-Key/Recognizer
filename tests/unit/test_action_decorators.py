"""Tests de los decoradores de acciones: gate, debounce y log."""

import logging

import pytest

from recognizer.core.actions.decorators import (
    ActionGate,
    DebouncedAction,
    GatedAction,
    LoggedAction,
)
from recognizer.core.constants import ACTION_LOGGER_NAME
from recognizer.core.domain.action import ActionContext
from recognizer.core.domain.gesture import GestureName
from recognizer.core.domain.hand import Handedness

GESTURE_CONFIDENCE = 0.9
TIMESTAMP = 1.0
COOLDOWN_SECONDS = 1.0


class RecordingAction:
    """Doble de Action que acumula los contextos ejecutados."""

    def __init__(self) -> None:
        self.contexts: list[ActionContext] = []

    def execute(self, context: ActionContext) -> None:
        self.contexts.append(context)


class FakeClock:
    """Reloj manual que solo avanza cuando el test lo indica."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _context() -> ActionContext:
    return ActionContext(
        gesture=GestureName.VICTORY,
        confidence=GESTURE_CONFIDENCE,
        handedness=Handedness.RIGHT,
        timestamp=TIMESTAMP,
    )


def test_gate_toggle_alternates_state() -> None:
    gate = ActionGate()

    assert gate.enabled
    assert gate.toggle() is False
    assert not gate.enabled
    assert gate.toggle() is True
    assert gate.enabled


def test_gated_actions_share_gate_and_stop_together() -> None:
    gate = ActionGate()
    first_inner = RecordingAction()
    second_inner = RecordingAction()
    first = GatedAction(first_inner, gate=gate)
    second = GatedAction(second_inner, gate=gate)
    context = _context()

    first.execute(context)
    second.execute(context)
    assert first_inner.contexts == [context]
    assert second_inner.contexts == [context]
    assert first.enabled
    assert second.enabled

    gate.toggle()
    first.execute(context)
    second.execute(context)
    assert first_inner.contexts == [context]
    assert second_inner.contexts == [context]
    assert not first.enabled
    assert not second.enabled


def test_debounced_action_skips_executions_within_cooldown() -> None:
    inner = RecordingAction()
    clock = FakeClock()
    debounced = DebouncedAction(inner, cooldown_seconds=COOLDOWN_SECONDS, clock=clock)
    context = _context()

    debounced.execute(context)
    assert inner.contexts == [context]

    clock.now = COOLDOWN_SECONDS / 2
    debounced.execute(context)
    assert inner.contexts == [context]

    clock.now = COOLDOWN_SECONDS
    debounced.execute(context)
    assert inner.contexts == [context, context]


def test_logged_action_logs_gesture_and_delegates(caplog: pytest.LogCaptureFixture) -> None:
    inner = RecordingAction()
    logged = LoggedAction(inner)
    context = _context()

    with caplog.at_level(logging.INFO, logger=ACTION_LOGGER_NAME):
        logged.execute(context)

    assert inner.contexts == [context]
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == logging.INFO
    assert record.name == ACTION_LOGGER_NAME
    assert GestureName.VICTORY.value in record.getMessage()
    assert "RecordingAction" in record.getMessage()
