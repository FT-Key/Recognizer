"""Tests del dominio de acciones: valores del enum e inmutabilidad."""

from dataclasses import FrozenInstanceError

import pytest

from recognizer.core.domain.action import ActionContext, MediaKey
from recognizer.core.domain.gesture import GESTURE_NONE, GESTURE_VICTORY
from recognizer.core.domain.hand import Handedness

GESTURE_CONFIDENCE = 0.9
TIMESTAMP = 1.5


def test_media_key_values() -> None:
    assert MediaKey.VOLUME_UP.value == "volume_up"
    assert MediaKey.VOLUME_DOWN.value == "volume_down"
    assert MediaKey.VOLUME_MUTE.value == "volume_mute"
    assert MediaKey.PLAY_PAUSE.value == "play_pause"
    assert MediaKey.NEXT_TRACK.value == "next_track"
    assert MediaKey.PREVIOUS_TRACK.value == "previous_track"
    assert {member.value for member in MediaKey} == {
        "volume_up",
        "volume_down",
        "volume_mute",
        "play_pause",
        "next_track",
        "previous_track",
    }


def test_action_context_keeps_fields() -> None:
    context = ActionContext(
        gesture=GESTURE_VICTORY,
        confidence=GESTURE_CONFIDENCE,
        handedness=Handedness.RIGHT,
        timestamp=TIMESTAMP,
    )

    assert context.gesture is GESTURE_VICTORY
    assert context.confidence == GESTURE_CONFIDENCE
    assert context.handedness is Handedness.RIGHT
    assert context.timestamp == TIMESTAMP


def test_action_context_is_immutable() -> None:
    context = ActionContext(
        gesture=GESTURE_VICTORY,
        confidence=GESTURE_CONFIDENCE,
        handedness=Handedness.RIGHT,
        timestamp=TIMESTAMP,
    )
    with pytest.raises(FrozenInstanceError):
        context.__setattr__("gesture", GESTURE_NONE)
