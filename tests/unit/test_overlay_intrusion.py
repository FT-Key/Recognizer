"""Tests del overlay del anti-intrusos sobre fotogramas sinteticos (sin hardware)."""

import numpy as np
from numpy.typing import NDArray

from recognizer.adapters.overlay_intrusion import (
    ALERT_COLOR_BGR,
    BOX_COLOR_BGR,
    HUD_COLOR_BGR,
    INTRUDER_BOX_COLOR_BGR,
    ZONE_ALERT_COLOR_BGR,
    ZONE_OK_COLOR_BGR,
    draw_intrusion_overlay,
)
from recognizer.core.domain.detection import BoundingBox, Detection
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.intrusion import IntrusionZone
from recognizer.core.domain.tracking import TrackedDetection

FRAME_HEIGHT = 480
FRAME_WIDTH = 640
ZONE = IntrusionZone(x_min=0.2, y_min=0.2, x_max=0.8, y_max=0.8)
ZONE_PIXEL_X = int(ZONE.x_min * FRAME_WIDTH)
ZONE_PIXEL_Y = int(ZONE.y_min * FRAME_HEIGHT)
INTRUDER_BOX = (0.4, 0.4, 0.6, 0.6)
OTHER_BOX = (0.1, 0.1, 0.2, 0.2)
INTRUDER_TRACK_ID = 1
OTHER_TRACK_ID = 2


def _frame() -> Frame:
    data: NDArray[np.uint8] = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)
    return Frame(data=data, timestamp=0.0)


def _tracked(track_id: int, box: tuple[float, float, float, float]) -> TrackedDetection:
    bbox = BoundingBox(x_min=box[0], y_min=box[1], x_max=box[2], y_max=box[3])
    detection = Detection(label="person", confidence=0.9, bbox=bbox)
    return TrackedDetection(track_id=track_id, detection=detection)


def _box_pixel(box: tuple[float, float, float, float]) -> tuple[int, int]:
    return int(box[0] * FRAME_WIDTH), int(box[1] * FRAME_HEIGHT)


def _color_mask(data: NDArray[np.uint8], color: tuple[int, int, int]) -> NDArray[np.bool_]:
    return np.all(data == np.array(color, dtype=np.uint8), axis=-1)


def test_draw_intrusion_overlay_draws_zone_and_hud() -> None:
    frame = _frame()

    draw_intrusion_overlay(
        frame.data,
        tracked=(),
        zone=ZONE,
        active=False,
        intruder_ids=frozenset(),
    )

    assert frame.data[ZONE_PIXEL_Y, ZONE_PIXEL_X].tolist() == list(ZONE_OK_COLOR_BGR)
    assert _color_mask(frame.data, HUD_COLOR_BGR).any()
    assert not _color_mask(frame.data, ZONE_ALERT_COLOR_BGR).any()


def test_draw_intrusion_overlay_zone_turns_red_when_active() -> None:
    frame = _frame()

    draw_intrusion_overlay(
        frame.data,
        tracked=(),
        zone=ZONE,
        active=True,
        intruder_ids=frozenset(),
    )

    assert frame.data[ZONE_PIXEL_Y, ZONE_PIXEL_X].tolist() == list(ZONE_ALERT_COLOR_BGR)


def test_draw_intrusion_overlay_marks_only_intruder_box_red() -> None:
    frame = _frame()
    intruder = _tracked(INTRUDER_TRACK_ID, INTRUDER_BOX)
    other = _tracked(OTHER_TRACK_ID, OTHER_BOX)

    draw_intrusion_overlay(
        frame.data,
        tracked=(intruder, other),
        zone=None,
        active=True,
        intruder_ids=frozenset({INTRUDER_TRACK_ID}),
    )

    intruder_x, intruder_y = _box_pixel(INTRUDER_BOX)
    other_x, other_y = _box_pixel(OTHER_BOX)
    assert frame.data[intruder_y, intruder_x].tolist() == list(INTRUDER_BOX_COLOR_BGR)
    assert frame.data[other_y, other_x].tolist() == list(BOX_COLOR_BGR)


def test_draw_intrusion_overlay_draws_alert_banner_when_active() -> None:
    frame = _frame()

    draw_intrusion_overlay(
        frame.data,
        tracked=(),
        zone=None,
        active=True,
        intruder_ids=frozenset(),
    )

    assert _color_mask(frame.data, ALERT_COLOR_BGR).any()


def test_draw_intrusion_overlay_without_zone_or_intrusion_has_no_alert_color() -> None:
    frame = _frame()

    draw_intrusion_overlay(
        frame.data,
        tracked=(),
        zone=None,
        active=False,
        intruder_ids=frozenset(),
    )

    assert _color_mask(frame.data, HUD_COLOR_BGR).any()
    assert not _color_mask(frame.data, ALERT_COLOR_BGR).any()
