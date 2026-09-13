"""Overlay de landmarks de manos dibujado con OpenCV."""

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.core.domain.gesture import StableGesture
from recognizer.core.domain.hand import (
    HAND_CONNECTIONS,
    HAND_LANDMARK_COUNT,
    WRIST_LANDMARK_INDEX,
    Handedness,
    HandLandmarks,
)
from recognizer.core.domain.pointer import PointerPosition
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
GESTURE_COLOR_BGR = (0, 165, 255)
GESTURE_TEXT_OFFSET_PIXELS = 24
POINTER_COLOR_BGR = (255, 0, 255)
POINTER_RADIUS_PIXELS = 12
POINTER_THICKNESS = 2
POINTER_TEXT_OFFSET_PIXELS = 24


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


def _find_hand(
    *,
    hands: tuple[HandLandmarks, ...],
    handedness: Handedness,
) -> HandLandmarks | None:
    for hand in hands:
        if hand.handedness is handedness:
            return hand
    return None


def _draw_gesture(
    *,
    data: NDArray[np.uint8],
    hand: HandLandmarks,
    gesture: StableGesture,
) -> None:
    height, width = data.shape[:2]
    wrist = hand.points[WRIST_LANDMARK_INDEX]
    position = (
        int(wrist.x * width),
        max(int(wrist.y * height) - GESTURE_TEXT_OFFSET_PIXELS, 0),
    )
    label = f"{gesture.name.value} {gesture.confidence:.2f}"
    cv2.putText(
        data,
        label,
        position,
        TEXT_FONT,
        TEXT_SCALE,
        GESTURE_COLOR_BGR,
        TEXT_THICKNESS,
    )


class GestureOverlay(Processor):
    """Dibuja el gesto confirmado de cada mano encima de su muneca."""

    def process(self, context: FrameContext) -> FrameContext:
        """Dibuja los gestos confirmados; sin gestos o sin mano no hace nada."""
        for gesture in context.gestures:
            hand = _find_hand(hands=context.hands, handedness=gesture.handedness)
            if hand is not None and len(hand.points) > WRIST_LANDMARK_INDEX:
                _draw_gesture(data=context.frame.data, hand=hand, gesture=gesture)
        return context


def _draw_pointer(*, data: NDArray[np.uint8], position: PointerPosition) -> None:
    height, width = data.shape[:2]
    center_x = round(position.x * (width - 1))
    center_y = round(position.y * (height - 1))
    cv2.circle(
        data,
        (center_x, center_y),
        POINTER_RADIUS_PIXELS,
        POINTER_COLOR_BGR,
        POINTER_THICKNESS,
    )
    cv2.line(
        data,
        (center_x - POINTER_RADIUS_PIXELS, center_y),
        (center_x + POINTER_RADIUS_PIXELS, center_y),
        POINTER_COLOR_BGR,
        POINTER_THICKNESS,
    )
    cv2.line(
        data,
        (center_x, center_y - POINTER_RADIUS_PIXELS),
        (center_x, center_y + POINTER_RADIUS_PIXELS),
        POINTER_COLOR_BGR,
        POINTER_THICKNESS,
    )
    label = f"Puntero {position.x:.2f},{position.y:.2f}"
    cv2.putText(
        data,
        label,
        (center_x + POINTER_TEXT_OFFSET_PIXELS, center_y),
        TEXT_FONT,
        TEXT_SCALE,
        POINTER_COLOR_BGR,
        TEXT_THICKNESS,
    )


class PointerOverlay(Processor):
    """Dibuja la cruz y las coordenadas del puntero cuando esta activo."""

    def process(self, context: FrameContext) -> FrameContext:
        """Dibuja el puntero; sin posicion no hace nada."""
        if context.pointer is not None:
            _draw_pointer(data=context.frame.data, position=context.pointer)
        return context
