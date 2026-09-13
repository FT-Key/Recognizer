"""Prueba de integracion del clasificador real de gestos (sin camara)."""

import numpy as np
import pytest
from numpy.typing import NDArray

from recognizer.adapters.mediapipe_gesture_classifier import MediaPipeGestureClassifier
from recognizer.core.config import GestureConfig
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.gesture import GestureRecognition

pytestmark = pytest.mark.integration

FRAME_SHAPE = (480, 640, 3)


def test_real_classifier_on_black_frame_returns_no_gestures() -> None:
    config = GestureConfig()
    data: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    frame = Frame(data=data, timestamp=0.0)

    classifier = MediaPipeGestureClassifier(config)
    classifier.open()
    try:
        recognition = classifier.classify(frame)
    finally:
        classifier.close()

    assert isinstance(recognition, GestureRecognition)
    assert recognition.hands == ()
    assert recognition.detections == ()
