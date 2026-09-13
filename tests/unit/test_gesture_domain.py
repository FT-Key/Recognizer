"""Tests del dominio de gestos: valores del enum e inmutabilidad."""

from dataclasses import FrozenInstanceError

import pytest

from recognizer.core.domain.gesture import (
    DetectedGesture,
    GestureName,
    GestureRecognition,
    StableGesture,
)
from recognizer.core.domain.hand import Handedness, HandLandmarks, Point

GESTURE_CONFIDENCE = 0.9


def test_gesture_name_values() -> None:
    assert GestureName.NONE.value == "None"
    assert GestureName.CLOSED_FIST.value == "Closed_Fist"
    assert GestureName.OPEN_PALM.value == "Open_Palm"
    assert GestureName.POINTING_UP.value == "Pointing_Up"
    assert GestureName.THUMB_DOWN.value == "Thumb_Down"
    assert GestureName.THUMB_UP.value == "Thumb_Up"
    assert GestureName.VICTORY.value == "Victory"
    assert GestureName.I_LOVE_YOU.value == "ILoveYou"
    assert {member.value for member in GestureName} == {
        "None",
        "Closed_Fist",
        "Open_Palm",
        "Pointing_Up",
        "Thumb_Down",
        "Thumb_Up",
        "Victory",
        "ILoveYou",
    }


def test_detected_gesture_is_immutable() -> None:
    gesture = DetectedGesture(
        name=GestureName.VICTORY,
        confidence=GESTURE_CONFIDENCE,
        handedness=Handedness.RIGHT,
    )
    with pytest.raises(FrozenInstanceError):
        gesture.__setattr__("name", GestureName.NONE)


def test_stable_gesture_is_immutable() -> None:
    gesture = StableGesture(
        name=GestureName.OPEN_PALM,
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
        name=GestureName.VICTORY,
        confidence=GESTURE_CONFIDENCE,
        handedness=Handedness.RIGHT,
    )

    recognition = GestureRecognition(hands=(hand,), detections=(detection,))

    assert recognition.hands[0] is hand
    assert recognition.detections[0] is detection
