"""Tests del overlay facial sobre imagenes sinteticas, sin hardware.

Sigue el estilo de ``test_overlay_people.py``: se verifica que dibujar no
crashea y que los pixeles cambian (caja, HUD y guia).
"""

import numpy as np
from numpy.typing import NDArray

from recognizer.adapters.overlay_face import (
    SUCCESS_COLOR_BGR,
    SURFACE_COLOR_BGR,
    TARGET_FRAME_LABEL,
    draw_face_overlay,
)
from recognizer.core.constants import DEFAULT_MIN_FACE_WIDTH_RATIO
from recognizer.core.domain.face import CaptureGuidance, FaceBox, assess_capture

FRAME_HEIGHT = 480
FRAME_WIDTH = 640
BOX_X_MIN = 0.25
BOX_Y_MIN = 0.25
BOX_X_MAX = 0.5
BOX_Y_MAX = 0.5
BOX_PIXEL_X_MIN = int(BOX_X_MIN * FRAME_WIDTH)
BOX_PIXEL_Y_MIN = int(BOX_Y_MIN * FRAME_HEIGHT)
CONFIDENCE = 0.9


def _image() -> NDArray[np.uint8]:
    return np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)


def _box() -> FaceBox:
    return FaceBox(
        x_min=BOX_X_MIN,
        y_min=BOX_Y_MIN,
        x_max=BOX_X_MAX,
        y_max=BOX_Y_MAX,
        confidence=CONFIDENCE,
    )


def _color_mask(data: NDArray[np.uint8], color: tuple[int, int, int]) -> NDArray[np.bool_]:
    return np.all(data == np.array(color, dtype=np.uint8), axis=-1)


def test_draw_face_overlay_with_box_does_not_crash_and_paints() -> None:
    image = _image()
    before = image.copy()

    draw_face_overlay(
        image,
        boxes=(_box(),),
        guidance=CaptureGuidance.GOOD,
        progress_text="Muestras 1/5",
        login_text="",
        highlight_ok=True,
        target_width_ratio=0.18,
    )

    assert (image != before).any()
    assert image[BOX_PIXEL_Y_MIN, BOX_PIXEL_X_MIN].tolist() == list(SUCCESS_COLOR_BGR)


def test_draw_face_overlay_empty_boxes_still_draws_guide() -> None:
    image = _image()
    before = image.copy()

    draw_face_overlay(
        image,
        boxes=(),
        guidance=None,
        progress_text="",
        login_text="",
        highlight_ok=False,
        target_width_ratio=0.18,
    )

    assert (image != before).any()
    assert _color_mask(image, SURFACE_COLOR_BGR).any()


def test_draw_face_overlay_without_target_ratio_draws_no_frame() -> None:
    image = _image()
    before = image.copy()

    draw_face_overlay(
        image,
        boxes=(),
        guidance=None,
        progress_text="",
        login_text="",
        highlight_ok=False,
    )

    assert (image == before).all()


def test_draw_face_overlay_target_frame_matches_ratio() -> None:
    ratio = 0.18
    image = _image()

    draw_face_overlay(
        image,
        boxes=(),
        guidance=None,
        progress_text="",
        login_text="",
        highlight_ok=False,
        target_width_ratio=ratio,
    )

    side = int(FRAME_WIDTH * ratio)
    x_min = (FRAME_WIDTH - side) // 2
    y_min = (FRAME_HEIGHT - side) // 2
    assert image[y_min, x_min].tolist() == list(SURFACE_COLOR_BGR)
    assert TARGET_FRAME_LABEL


def test_draw_face_overlay_login_text_paints_hud() -> None:
    image = _image()

    draw_face_overlay(
        image,
        boxes=(),
        guidance=CaptureGuidance.MOVE_CLOSER,
        progress_text="",
        login_text="Bienvenido Ada F-0001",
        highlight_ok=True,
    )

    assert _color_mask(image, SUCCESS_COLOR_BGR).any()


def test_assess_capture_with_default_min_ratio_boundaries() -> None:
    sharp = 100.0

    def _centered(width: float) -> FaceBox:
        half = width / 2.0
        return FaceBox(
            x_min=0.5 - half,
            y_min=0.5 - half,
            x_max=0.5 + half,
            y_max=0.5 + half,
            confidence=CONFIDENCE,
        )

    assert DEFAULT_MIN_FACE_WIDTH_RATIO == 0.18
    assert (
        assess_capture(_centered(DEFAULT_MIN_FACE_WIDTH_RATIO - 0.01), sharp)
        is CaptureGuidance.MOVE_CLOSER
    )
    assert (
        assess_capture(_centered(DEFAULT_MIN_FACE_WIDTH_RATIO + 0.02), sharp)
        is CaptureGuidance.GOOD
    )
    assert assess_capture(_centered(0.8), sharp) is CaptureGuidance.MOVE_FARTHER


def test_draw_face_overlay_guidance_text_paints_footer() -> None:
    plain = _image()
    draw_face_overlay(
        plain,
        boxes=(),
        guidance=None,
        progress_text="",
        login_text="",
        highlight_ok=False,
    )
    guided = _image()
    draw_face_overlay(
        guided,
        boxes=(),
        guidance=CaptureGuidance.MOVE_FARTHER,
        progress_text="",
        login_text="",
        highlight_ok=False,
    )

    assert (guided != plain).any()
