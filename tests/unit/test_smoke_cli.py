"""Tests del CLI de smoke sin camara real (doble verificacion previa a side effects)."""

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from recognizer.cli import smoke
from recognizer.core.config import GestureConfig
from recognizer.core.domain.events import (
    DomainEvent,
    GestureDetected,
    GestureReleased,
    HandsDetected,
)
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.gesture import (
    DetectedGesture,
    GestureName,
    GestureRecognition,
    StableGesture,
)
from recognizer.core.domain.hand import (
    HAND_LANDMARK_COUNT,
    Handedness,
    HandLandmarks,
    Point,
)
from recognizer.core.ports.event_bus import EventT

EXPECTED_FAILURE_CODE = 1
FRAME_TIMESTAMP = 2.0
FRAME_SHAPE = (4, 6, 3)
HAND_CONFIDENCE = 0.9
GESTURE_CONFIDENCE = 0.8
MIN_GESTURE_CONFIDENCE = 0.5
STATS_HIGH_CONFIDENCE = 0.9
TWO_HANDS = 2


class FakeClassifier:
    """Doble de GestureClassifier con una clasificacion predefinida."""

    def __init__(self, recognition: GestureRecognition) -> None:
        self.recognition = recognition
        self.classified_frames: list[Frame] = []

    def open(self) -> None:
        pass

    def classify(self, frame: Frame) -> GestureRecognition:
        self.classified_frames.append(frame)
        return self.recognition

    def close(self) -> None:
        pass


class RecordingBus:
    """Doble de EventBus que acumula los eventos publicados."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    def subscribe(self, event_type: type[EventT], handler: Callable[[EventT], None]) -> None:
        del event_type, handler

    def publish(self, event: DomainEvent) -> None:
        self.events.append(event)


def _frame() -> Frame:
    data: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    return Frame(data=data, timestamp=FRAME_TIMESTAMP)


def _hand() -> HandLandmarks:
    point = Point(x=0.5, y=0.5, z=0.0)
    return HandLandmarks(
        handedness=Handedness.RIGHT,
        confidence=HAND_CONFIDENCE,
        points=(point,) * HAND_LANDMARK_COUNT,
    )


def _recognition() -> GestureRecognition:
    detection = DetectedGesture(
        name=GestureName.VICTORY,
        confidence=GESTURE_CONFIDENCE,
        handedness=Handedness.RIGHT,
    )
    return GestureRecognition(hands=(_hand(),), detections=(detection,))


def test_main_without_window_and_default_frames_fails_before_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(path: Path) -> object:
        del path
        msg = "load_config no debe llamarse sin --frames."
        raise AssertionError(msg)

    class FailingCamera:
        """Doble que falla si el smoke intenta abrir la camara."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs
            msg = "La camara no debe abrirse sin --frames."
            raise AssertionError(msg)

    monkeypatch.setattr(smoke, "load_config", fail_if_called)
    monkeypatch.setattr(smoke, "OpenCVCamera", FailingCamera)

    assert smoke.main(["--no-window"]) == EXPECTED_FAILURE_CODE


def test_gesture_stats_handle_updates_counters() -> None:
    stats = smoke._GestureStats()
    hand = _hand()

    stats.handle(HandsDetected(timestamp=0.1, hands=(hand,)))
    stats.handle(HandsDetected(timestamp=0.2, hands=(hand, hand)))
    stats.handle(
        GestureDetected(
            timestamp=0.3,
            gesture=GestureName.VICTORY,
            confidence=STATS_HIGH_CONFIDENCE,
            handedness=Handedness.RIGHT,
        )
    )
    stats.handle(
        GestureDetected(
            timestamp=0.4,
            gesture=GestureName.VICTORY,
            confidence=STATS_HIGH_CONFIDENCE,
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


def test_build_pipeline_with_classifier_detects_and_stabilizes() -> None:
    recognition = _recognition()
    classifier = FakeClassifier(recognition)
    bus = RecordingBus()
    gestures = GestureConfig(
        stabilization_frames=1,
        min_gesture_confidence=MIN_GESTURE_CONFIDENCE,
    )
    pipeline = smoke._build_pipeline(classifier=classifier, bus=bus, gestures=gestures)
    frame = _frame()

    context = pipeline.run(frame)

    assert context.frame is frame
    assert context.hands == recognition.hands
    assert context.detections == recognition.detections
    assert context.gestures == (
        StableGesture(
            name=GestureName.VICTORY,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.RIGHT,
        ),
    )
    assert classifier.classified_frames == [frame]
    assert bus.events == [
        HandsDetected(timestamp=FRAME_TIMESTAMP, hands=recognition.hands),
        GestureDetected(
            timestamp=FRAME_TIMESTAMP,
            gesture=GestureName.VICTORY,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.RIGHT,
        ),
    ]


def test_build_pipeline_without_classifier_is_empty() -> None:
    bus = RecordingBus()
    pipeline = smoke._build_pipeline(classifier=None, bus=bus, gestures=GestureConfig())

    context = pipeline.run(_frame())

    assert context.hands == ()
    assert context.detections == ()
    assert context.gestures == ()
    assert bus.events == []
