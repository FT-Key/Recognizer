"""Overlay de landmarks de manos dibujado con OpenCV."""

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.core.domain.hand import (
    HAND_CONNECTIONS,
    HAND_LANDMARK_COUNT,
    WRIST_LANDMARK_INDEX,
    HandLandmarks,
)
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.pipeline.processor import Processor

CONNECTION_COLOR_BGR = (0, 200, 0)
CONNECTION_THICKNESS = 2
LANDMARK_COLOR_BGR = (0, 0, 255)
LANDMARK_RADIUS = 3
LANDMARK_THICKNESS = -1
TEXT_COLOR_BGR = (255, 255, 0)
TEXT_FONT = cv2.FONT_HERSHEY_SIMPLEX
TEXT_SCALE = 0.5
TEXT_THICKNESS = 1
TEXT_OFFSET_PIXELS = 8


def _draw_hand(*, data: NDArray[np.uint8], hand: HandLandmarks) -> None:
    height, width = data.shape[:2]
    points = [(int(point.x * width), int(point.y * height)) for point in hand.points]

    for start, end in HAND_CONNECTIONS:
        cv2.line(data, points[start], points[end], CONNECTION_COLOR_BGR, CONNECTION_THICKNESS)
    for point in points:
        cv2.circle(data, point, LANDMARK_RADIUS, LANDMARK_COLOR_BGR, LANDMARK_THICKNESS)

    wrist_x, wrist_y = points[WRIST_LANDMARK_INDEX]
    label = f"{hand.handedness.value} {hand.confidence:.2f}"
    cv2.putText(
        data,
        label,
        (wrist_x + TEXT_OFFSET_PIXELS, wrist_y),
        TEXT_FONT,
        TEXT_SCALE,
        TEXT_COLOR_BGR,
        TEXT_THICKNESS,
    )


class LandmarkOverlay(Processor):
    """Dibuja conexiones, puntos y etiqueta de cada mano sobre el fotograma."""

    def process(self, context: FrameContext) -> FrameContext:
        """Dibuja las manos detectadas; sin manos no hace nada."""
        for hand in context.hands:
            if len(hand.points) == HAND_LANDMARK_COUNT:
                _draw_hand(data=context.frame.data, hand=hand)
        return context
