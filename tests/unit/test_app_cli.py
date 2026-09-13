"""Tests del CLI de la app local, sin camara real ni acciones externas."""

from collections import Counter
from pathlib import Path

import pytest

from recognizer.cli import app
from recognizer.core.actions.decorators import ActionGate
from recognizer.core.domain.events import (
    GestureDetected,
    GestureReleased,
    HandsDetected,
)
from recognizer.core.domain.gesture import GestureName
from recognizer.core.domain.hand import Handedness, HandLandmarks, Point

EXPECTED_FAILURE_CODE = 1
GESTURE_CONFIDENCE = 0.8
HAND_CONFIDENCE = 0.9
TWO_HANDS = 2
DEFAULT_CONFIG = Path("config.yaml")


def _hand() -> HandLandmarks:
    return HandLandmarks(
        handedness=Handedness.RIGHT,
        confidence=HAND_CONFIDENCE,
        points=(Point(x=0.5, y=0.5, z=0.0),),
    )


def test_parser_defaults() -> None:
    args = app._build_parser().parse_args([])

    assert args.config == DEFAULT_CONFIG
    assert args.device is None
    assert args.frames == 0
    assert args.no_window is False
    assert args.no_actions is False


def test_parser_reads_all_flags() -> None:
    args = app._build_parser().parse_args(
        [
            "--config",
            "otra.yaml",
            "--device",
            "2",
            "--frames",
            "10",
            "--no-window",
            "--no-actions",
        ]
    )

    assert args.config == Path("otra.yaml")
    assert args.device == 2
    assert args.frames == 10
    assert args.no_window is True
    assert args.no_actions is True


def test_no_window_without_frames_fails_before_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(path: Path) -> object:
        del path
        msg = "load_config no debe llamarse sin --frames."
        raise AssertionError(msg)

    class FailingCamera:
        """Doble que falla si la app intenta abrir la camara."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs
            msg = "La camara no debe abrirse sin --frames."
            raise AssertionError(msg)

    monkeypatch.setattr(app, "load_config", fail_if_called)
    monkeypatch.setattr(app, "OpenCVCamera", FailingCamera)

    assert app.main(["--no-window"]) == EXPECTED_FAILURE_CODE


def test_stats_handle_updates_counters() -> None:
    stats = app._Stats()
    hand = _hand()

    stats.handle(HandsDetected(timestamp=0.1, hands=(hand,)))
    stats.handle(HandsDetected(timestamp=0.2, hands=(hand, hand)))
    stats.handle(
        GestureDetected(
            timestamp=0.3,
            gesture=GestureName.VICTORY,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.RIGHT,
        )
    )
    stats.handle(
        GestureDetected(
            timestamp=0.4,
            gesture=GestureName.VICTORY,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.RIGHT,
        )
    )
    stats.handle(
        GestureDetected(
            timestamp=0.5,
            gesture=GestureName.OPEN_PALM,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.LEFT,
        )
    )
    stats.handle(
        GestureReleased(
            timestamp=0.6,
            gesture=GestureName.VICTORY,
            handedness=Handedness.RIGHT,
        )
    )

    assert stats.hands_events == 2
    assert stats.max_hands == TWO_HANDS
    assert stats.detected_events == 3
    assert stats.released_events == 1
    assert stats.confirmed == {GestureName.VICTORY: 2, GestureName.OPEN_PALM: 1}


def test_actions_state_without_gate_is_inactive() -> None:
    assert app._actions_state(None) == "inactivas"


def test_actions_state_reflects_gate() -> None:
    gate = ActionGate()

    assert app._actions_state(gate) == "activadas"
    gate.toggle()
    assert app._actions_state(gate) == "desactivadas"


def test_format_confirmed_without_gestures() -> None:
    assert app._format_confirmed(Counter()) == app.NO_CONFIRMED_GESTURES


def test_format_confirmed_lists_counts() -> None:
    confirmed: Counter[GestureName] = Counter({GestureName.VICTORY: 2, GestureName.OPEN_PALM: 1})

    assert app._format_confirmed(confirmed) == "Victory=2, Open_Palm=1"
