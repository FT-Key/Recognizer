"""Tests del overlay de landmarks sobre fotogramas sinteticos."""

import numpy as np
from numpy.typing import NDArray

from recognizer.adapters.overlay_opencv import (
    CONNECTION_COLOR_BGR,
    LANDMARK_COLOR_BGR,
    LandmarkOverlay,
)
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.hand import HAND_LANDMARK_COUNT, Handedness, HandLandmarks, Point
from recognizer.core.pipeline.context import FrameContext

FRAME_HEIGHT = 480
FRAME_WIDTH = 640
WRIST_X = 0.5
WRIST_Y = 0.5
INDEX_X = 0.5
INDEX_Y = 0.6
WRIST_PIXEL_X = int(WRIST_X * FRAME_WIDTH)
WRIST_PIXEL_Y = int(WRIST_Y * FRAME_HEIGHT)
CONNECTION_PIXEL_Y = int((WRIST_Y + INDEX_Y) / 2 * FRAME_HEIGHT)
SHORT_HAND_POINTS = 5
HAND_CONFIDENCE = 0.9


def _frame() -> Frame:
    data: NDArray[np.uint8] = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)
    return Frame(data=data, timestamp=0.0)


def _hand(points_count: int = HAND_LANDMARK_COUNT) -> HandLandmarks:
    points: list[Point] = [Point(x=WRIST_X, y=WRIST_Y, z=0.0) for _ in range(points_count)]
    if points_count > 1:
        points[1] = Point(x=INDEX_X, y=INDEX_Y, z=0.0)
    return HandLandmarks(
        handedness=Handedness.RIGHT,
        confidence=HAND_CONFIDENCE,
        points=tuple(points),
    )


def test_process_draws_landmark_and_connection_pixels() -> None:
    frame = _frame()
    context = FrameContext(frame=frame, hands=(_hand(),))

    result = LandmarkOverlay().process(context)

    assert result is context
    assert frame.data[WRIST_PIXEL_Y, WRIST_PIXEL_X].tolist() == list(LANDMARK_COLOR_BGR)
    assert frame.data[CONNECTION_PIXEL_Y, WRIST_PIXEL_X].tolist() == list(CONNECTION_COLOR_BGR)


def test_process_draws_non_zero_connection_pixels() -> None:
    frame = _frame()
    LandmarkOverlay().process(FrameContext(frame=frame, hands=(_hand(),)))

    connection = np.array(CONNECTION_COLOR_BGR, dtype=np.uint8)
    connection_mask = np.all(frame.data == connection, axis=-1)

    assert connection_mask.any()


def test_process_returns_same_context() -> None:
    context = FrameContext(frame=_frame(), hands=())
    assert LandmarkOverlay().process(context) is context


def test_short_hand_is_ignored() -> None:
    frame = _frame()
    context = FrameContext(frame=frame, hands=(_hand(points_count=SHORT_HAND_POINTS),))

    result = LandmarkOverlay().process(context)

    assert result is context
    assert not frame.data.any()


def test_no_hands_leaves_frame_untouched() -> None:
    frame = _frame()

    LandmarkOverlay().process(FrameContext(frame=frame, hands=()))

    assert not frame.data.any()
