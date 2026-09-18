"""Tests del overlay del contador de personas sobre fotogramas sinteticos.

Sigue el estilo de ``test_overlay_opencv.py``: se verifica el color de pixeles
concretos y la presencia de mascaras de color, sin hardware real.
"""

import numpy as np
from numpy.typing import NDArray

from recognizer.adapters.overlay_people import (
    BOX_COLOR_BGR,
    HUD_COLOR_BGR,
    LINE_COLOR_BGR,
    draw_people_overlay,
)
from recognizer.core.constants import PERSON_LABEL
from recognizer.core.domain.detection import BoundingBox, Detection
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.tracking import CountingLine, LineAxis, TrackedDetection

FRAME_HEIGHT = 480
FRAME_WIDTH = 640
LINE_POSITION = 0.5
LINE_PIXEL_Y = int(LINE_POSITION * FRAME_HEIGHT)
LINE_PIXEL_X = int(LINE_POSITION * FRAME_WIDTH)
SAMPLE_PIXEL = 10
TRACK_ID = 1
CONFIDENCE = 0.9
BOX_X_MIN = 0.5
BOX_Y_MIN = 0.4
BOX_X_MAX = 0.9
BOX_Y_MAX = 0.8
BOX_PIXEL_X_MIN = int(BOX_X_MIN * FRAME_WIDTH)
BOX_PIXEL_Y_MIN = int(BOX_Y_MIN * FRAME_HEIGHT)
BOX_PIXEL_X_MAX = int(BOX_X_MAX * FRAME_WIDTH)
BOX_PIXEL_Y_MAX = int(BOX_Y_MAX * FRAME_HEIGHT)
BOX_INTERIOR_MARGIN = 2


def _frame() -> Frame:
    data: NDArray[np.uint8] = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)
    return Frame(data=data, timestamp=0.0)


def _tracked() -> TrackedDetection:
    bbox = BoundingBox(x_min=BOX_X_MIN, y_min=BOX_Y_MIN, x_max=BOX_X_MAX, y_max=BOX_Y_MAX)
    detection = Detection(label=PERSON_LABEL, confidence=CONFIDENCE, bbox=bbox)
    return TrackedDetection(track_id=TRACK_ID, detection=detection)


def _color_mask(data: NDArray[np.uint8], color: tuple[int, int, int]) -> NDArray[np.bool_]:
    return np.all(data == np.array(color, dtype=np.uint8), axis=-1)


def test_draw_people_overlay_draws_box_and_hud() -> None:
    frame = _frame()

    draw_people_overlay(
        frame.data,
        tracked=(_tracked(),),
        current=1,
        entries=0,
        exits=0,
        line=None,
    )

    assert frame.data[BOX_PIXEL_Y_MIN, BOX_PIXEL_X_MIN].tolist() == list(BOX_COLOR_BGR)
    assert _color_mask(frame.data, HUD_COLOR_BGR).any()


def test_draw_people_overlay_draws_horizontal_line() -> None:
    frame = _frame()

    draw_people_overlay(
        frame.data,
        tracked=(),
        current=0,
        entries=0,
        exits=0,
        line=CountingLine(axis=LineAxis.HORIZONTAL, position=LINE_POSITION),
    )

    assert frame.data[LINE_PIXEL_Y, SAMPLE_PIXEL].tolist() == list(LINE_COLOR_BGR)


def test_draw_people_overlay_draws_vertical_line() -> None:
    frame = _frame()

    draw_people_overlay(
        frame.data,
        tracked=(),
        current=0,
        entries=0,
        exits=0,
        line=CountingLine(axis=LineAxis.VERTICAL, position=LINE_POSITION),
    )

    assert frame.data[SAMPLE_PIXEL, LINE_PIXEL_X].tolist() == list(LINE_COLOR_BGR)


def test_draw_people_overlay_without_line_and_tracks_draws_only_hud() -> None:
    frame = _frame()

    draw_people_overlay(
        frame.data,
        tracked=(),
        current=0,
        entries=2,
        exits=1,
        line=None,
    )

    assert _color_mask(frame.data, HUD_COLOR_BGR).any()
    assert not _color_mask(frame.data, LINE_COLOR_BGR).any()
    interior = frame.data[
        BOX_PIXEL_Y_MIN + BOX_INTERIOR_MARGIN : BOX_PIXEL_Y_MAX - BOX_INTERIOR_MARGIN,
        BOX_PIXEL_X_MIN + BOX_INTERIOR_MARGIN : BOX_PIXEL_X_MAX - BOX_INTERIOR_MARGIN,
    ]
    assert not interior.any()
