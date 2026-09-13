"""Prueba de integracion del tracker real de MediaPipe (sin camara)."""

import numpy as np
import pytest
from numpy.typing import NDArray

from recognizer.adapters.mediapipe_hand_tracker import MediaPipeHandTracker
from recognizer.core.config import HandsConfig
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.hand import HandLandmarks

pytestmark = pytest.mark.integration

FRAME_SHAPE = (480, 640, 3)


def test_real_tracker_on_black_frame_returns_empty_tuple() -> None:
    config = HandsConfig()
    data: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    frame = Frame(data=data, timestamp=0.0)

    tracker = MediaPipeHandTracker(config)
    tracker.open()
    try:
        hands = tracker.detect(frame)
    finally:
        tracker.close()

    assert isinstance(hands, tuple)
    assert all(isinstance(hand, HandLandmarks) for hand in hands)
    assert len(hands) <= config.max_hands
