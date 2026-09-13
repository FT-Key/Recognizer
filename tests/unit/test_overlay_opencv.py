"""Tests del overlay de landmarks sobre fotogramas sinteticos."""

import numpy as np
import pytest
from numpy.typing import NDArray

from recognizer.adapters.overlay_opencv import (
    CONNECTION_COLOR_BGR,
    GESTURE_COLOR_BGR,
    GESTURE_TEXT_OFFSET_PIXELS,
    LANDMARK_COLOR_BGR,
    POINTER_COLOR_BGR,
    POINTER_TEXT_OFFSET_PIXELS,
    GestureOverlay,
    LandmarkOverlay,
    PointerOverlay,
)
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.gesture import GestureName, StableGesture
from recognizer.core.domain.hand import HAND_LANDMARK_COUNT, Handedness, HandLandmarks, Point
from recognizer.core.domain.pointer import PointerPosition
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
GESTURE_CONFIDENCE = 0.87
GESTURE_OFFSET_Y = WRIST_PIXEL_Y - GESTURE_TEXT_OFFSET_PIXELS
TEXT_BOX_TOP_MARGIN_PIXELS = 20
TEXT_BOX_BOTTOM_MARGIN_PIXELS = 4
TEXT_BOX_WIDTH_PIXELS = 200


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


def _gesture(
    *,
    name: GestureName = GestureName.VICTORY,
    handedness: Handedness = Handedness.RIGHT,
) -> StableGesture:
    return StableGesture(name=name, confidence=GESTURE_CONFIDENCE, handedness=handedness)


def _gesture_color_mask(data: NDArray[np.uint8]) -> NDArray[np.bool_]:
    gesture_color = np.array(GESTURE_COLOR_BGR, dtype=np.uint8)
    return np.all(data == gesture_color, axis=-1)


def test_gesture_overlay_draws_text_over_wrist() -> None:
    frame = _frame()
    context = FrameContext(frame=frame, hands=(_hand(),), gestures=(_gesture(),))

    result = GestureOverlay().process(context)

    assert result is context
    top = max(GESTURE_OFFSET_Y - TEXT_BOX_TOP_MARGIN_PIXELS, 0)
    bottom = min(GESTURE_OFFSET_Y + TEXT_BOX_BOTTOM_MARGIN_PIXELS, FRAME_HEIGHT)
    right = min(WRIST_PIXEL_X + TEXT_BOX_WIDTH_PIXELS, FRAME_WIDTH)
    text_zone = frame.data[top:bottom, WRIST_PIXEL_X:right]
    assert _gesture_color_mask(text_zone).any()


def test_gesture_overlay_without_matching_hand_does_nothing() -> None:
    frame = _frame()
    context = FrameContext(
        frame=frame,
        hands=(_hand(),),
        gestures=(_gesture(handedness=Handedness.LEFT),),
    )

    result = GestureOverlay().process(context)

    assert result is context
    assert not frame.data.any()


def test_gesture_overlay_without_gestures_does_nothing() -> None:
    frame = _frame()
    context = FrameContext(frame=frame, hands=(_hand(),), gestures=())

    result = GestureOverlay().process(context)

    assert result is context
    assert not frame.data.any()


def test_gesture_overlay_without_hands_does_nothing() -> None:
    frame = _frame()
    context = FrameContext(frame=frame, hands=(), gestures=(_gesture(),))

    result = GestureOverlay().process(context)

    assert result is context
    assert not frame.data.any()


def test_gesture_overlay_with_empty_hand_points_does_nothing() -> None:
    frame = _frame()
    context = FrameContext(
        frame=frame,
        hands=(_hand(points_count=0),),
        gestures=(_gesture(),),
    )

    result = GestureOverlay().process(context)

    assert result is context
    assert not frame.data.any()


POINTER_X = 0.5
POINTER_Y = 0.5
POINTER_PIXEL_X = int(POINTER_X * FRAME_WIDTH)
POINTER_PIXEL_Y = int(POINTER_Y * FRAME_HEIGHT)
EXTREME_FRAME_WIDTH = 20
EXTREME_FRAME_HEIGHT = 10


def _pointer(x: float = POINTER_X, y: float = POINTER_Y) -> PointerPosition:
    return PointerPosition(x=x, y=y)


def _extreme_frame() -> Frame:
    data: NDArray[np.uint8] = np.zeros(
        (EXTREME_FRAME_HEIGHT, EXTREME_FRAME_WIDTH, 3), dtype=np.uint8
    )
    return Frame(data=data, timestamp=0.0)


def test_pointer_overlay_without_pointer_does_nothing() -> None:
    frame = _frame()
    context = FrameContext(frame=frame, pointer=None)

    result = PointerOverlay().process(context)

    assert result is context
    assert not frame.data.any()


def test_pointer_overlay_draws_cross_and_label() -> None:
    frame = _frame()
    context = FrameContext(frame=frame, pointer=_pointer())

    result = PointerOverlay().process(context)

    assert result is context
    pointer_color = np.array(POINTER_COLOR_BGR, dtype=np.uint8)
    mask = np.all(frame.data == pointer_color, axis=-1)
    assert mask.any()
    assert mask[POINTER_PIXEL_Y, POINTER_PIXEL_X]
    label_top = max(POINTER_PIXEL_Y - POINTER_TEXT_OFFSET_PIXELS, 0)
    label_x = POINTER_PIXEL_X + POINTER_TEXT_OFFSET_PIXELS
    label_zone = mask[label_top : POINTER_PIXEL_Y + 1, label_x:]
    assert label_zone.any()


@pytest.mark.parametrize(
    ("x", "y", "pixel_x", "pixel_y"),
    [
        (0.0, 0.0, 0, 0),
        (1.0, 1.0, EXTREME_FRAME_WIDTH - 1, EXTREME_FRAME_HEIGHT - 1),
    ],
)
def test_pointer_overlay_places_cross_center_at_extreme_pixels(
    x: float,
    y: float,
    pixel_x: int,
    pixel_y: int,
) -> None:
    frame = _extreme_frame()
    context = FrameContext(frame=frame, pointer=_pointer(x=x, y=y))

    result = PointerOverlay().process(context)

    assert result is context
    assert frame.data[pixel_y, pixel_x].tolist() == list(POINTER_COLOR_BGR)
