"""Tests del dominio de gestos: valores predefinidos e inmutabilidad."""

from dataclasses import FrozenInstanceError

import pytest

from recognizer.core.domain.gesture import (
    CANNED_GESTURE_LABELS,
    CANNED_GESTURES,
    GESTURE_CLOSED_FIST,
    GESTURE_ILOVE_YOU,
    GESTURE_NONE,
    GESTURE_OPEN_PALM,
    GESTURE_POINTING_UP,
    GESTURE_THUMB_DOWN,
    GESTURE_THUMB_UP,
    GESTURE_VICTORY,
    DetectedGesture,
    GestureRecognition,
    StableGesture,
)
from recognizer.core.domain.hand import Handedness, HandLandmarks, Point

GESTURE_CONFIDENCE = 0.9


def test_canned_gesture_values() -> None:
    assert GESTURE_NONE.value == "None"
    assert GESTURE_CLOSED_FIST.value == "Closed_Fist"
    assert GESTURE_OPEN_PALM.value == "Open_Palm"
    assert GESTURE_POINTING_UP.value == "Pointing_Up"
    assert GESTURE_THUMB_DOWN.value == "Thumb_Down"
    assert GESTURE_THUMB_UP.value == "Thumb_Up"
    assert GESTURE_VICTORY.value == "Victory"
    assert GESTURE_ILOVE_YOU.value == "ILoveYou"


def test_canned_gestures_exclude_none_and_match_labels() -> None:
    assert GESTURE_NONE not in CANNED_GESTURES
    assert {gesture.value for gesture in CANNED_GESTURES} == CANNED_GESTURE_LABELS
    assert "None" not in CANNED_GESTURE_LABELS
    assert len(CANNED_GESTURES) == len(set(CANNED_GESTURES))


def test_detected_gesture_is_immutable() -> None:
    gesture = DetectedGesture(
        name=GESTURE_VICTORY,
        confidence=GESTURE_CONFIDENCE,
        handedness=Handedness.RIGHT,
    )
    with pytest.raises(FrozenInstanceError):
        gesture.__setattr__("name", GESTURE_NONE)


def test_stable_gesture_is_immutable() -> None:
    gesture = StableGesture(
        name=GESTURE_OPEN_PALM,
        confidence=GESTURE_CONFIDENCE,
        handedness=Handedness.LEFT,
    )
    with pytest.raises(FrozenInstanceError):
        gesture.__setattr__("confidence", 0.1)


def test_gesture_recognition_is_immutable() -> None:
    recognition = GestureRecognition(hands=(), detections=())
    with pytest.raises(FrozenInstanceError):
        recognition.__setattr__("hands", ())


def test_gesture_recognition_keeps_parallel_sequences() -> None:
    hand = HandLandmarks(
        handedness=Handedness.RIGHT,
        confidence=GESTURE_CONFIDENCE,
        points=(Point(x=0.5, y=0.5, z=0.0),),
    )
    detection = DetectedGesture(
        name=GESTURE_VICTORY,
        confidence=GESTURE_CONFIDENCE,
        handedness=Handedness.RIGHT,
    )

    recognition = GestureRecognition(hands=(hand,), detections=(detection,))

    assert recognition.hands[0] is hand
    assert recognition.detections[0] is detection
