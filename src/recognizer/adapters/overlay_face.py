"""Overlay facial estilo vintage: cajas, HUD superior y guia inferior."""

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.core.domain.face import CaptureGuidance, FaceBox

SUCCESS_COLOR_BGR = (0, 200, 0)
WARNING_COLOR_BGR = (0, 165, 255)
DANGER_COLOR_BGR = (0, 0, 255)
SURFACE_COLOR_BGR = (180, 180, 180)
BOX_THICKNESS = 2
GUIDE_BOX_THICKNESS = 1
LABEL_FONT = cv2.FONT_HERSHEY_SIMPLEX
LABEL_SCALE = 0.6
LABEL_THICKNESS = 1
LABEL_MARGIN_PX = 6
LABEL_TEMPLATE = "cara {confidence:.2f}"
HUD_FONT = cv2.FONT_HERSHEY_SIMPLEX
HUD_SCALE = 0.9
HUD_THICKNESS = 2
HUD_POSITION = (10, 30)
PROGRESS_POSITION = (10, 60)
GUIDE_FONT = cv2.FONT_HERSHEY_SIMPLEX
GUIDE_SCALE = 0.8
GUIDE_THICKNESS = 2
GUIDE_MARGIN_PX = 20
GUIDE_BOX_PADDING_PX = 8
GUIDE_INSET_RATIO = 0.3


def _guidance_color(
    guidance: CaptureGuidance | None, *, highlight_ok: bool
) -> tuple[int, int, int]:
    """Color vintage segun el estado: verde si esta listo, ambar/rojo si no."""
    if guidance is None:
        return SURFACE_COLOR_BGR
    match guidance:
        case CaptureGuidance.GOOD:
            return SUCCESS_COLOR_BGR if highlight_ok else WARNING_COLOR_BGR
        case CaptureGuidance.CENTER_FACE | CaptureGuidance.HOLD_STILL:
            return WARNING_COLOR_BGR
        case _:
            return DANGER_COLOR_BGR


def _draw_boxes(
    image: NDArray[np.uint8],
    *,
    boxes: tuple[FaceBox, ...],
    width: int,
    height: int,
    color: tuple[int, int, int],
) -> None:
    for box in boxes:
        x_min = int(box.x_min * width)
        y_min = int(box.y_min * height)
        x_max = int(box.x_max * width)
        y_max = int(box.y_max * height)
        cv2.rectangle(image, (x_min, y_min), (x_max, y_max), color, BOX_THICKNESS)
        cv2.putText(
            image,
            LABEL_TEMPLATE.format(confidence=box.confidence),
            (x_min, max(y_min - LABEL_MARGIN_PX, 0)),
            LABEL_FONT,
            LABEL_SCALE,
            color,
            LABEL_THICKNESS,
        )


def _draw_distance_guide(
    image: NDArray[np.uint8],
    *,
    width: int,
    height: int,
    color: tuple[int, int, int],
) -> None:
    """Guia de distancia: marco central donde debe quedar la cara."""
    margin_x = int(width * GUIDE_INSET_RATIO)
    margin_y = int(height * GUIDE_INSET_RATIO)
    cv2.rectangle(
        image,
        (margin_x, margin_y),
        (width - margin_x, height - margin_y),
        color,
        GUIDE_BOX_THICKNESS,
    )


def draw_face_overlay(
    image: NDArray[np.uint8],
    *,
    boxes: tuple[FaceBox, ...],
    guidance: CaptureGuidance | None,
    progress_text: str,
    login_text: str,
    highlight_ok: bool,
) -> None:
    """Dibuja cajas faciales, HUD superior (login + progreso) y guia inferior."""
    height, width = image.shape[:2]
    color = _guidance_color(guidance, highlight_ok=highlight_ok)
    _draw_distance_guide(image, width=width, height=height, color=SURFACE_COLOR_BGR)
    _draw_boxes(image, boxes=boxes, width=width, height=height, color=color)
    if login_text:
        cv2.putText(
            image,
            login_text,
            HUD_POSITION,
            HUD_FONT,
            HUD_SCALE,
            SUCCESS_COLOR_BGR if highlight_ok else SURFACE_COLOR_BGR,
            HUD_THICKNESS,
        )
    if progress_text:
        cv2.putText(
            image,
            progress_text,
            PROGRESS_POSITION,
            HUD_FONT,
            HUD_SCALE,
            SURFACE_COLOR_BGR,
            HUD_THICKNESS,
        )
    if guidance is not None:
        text = guidance.value
        (text_width, text_height), _ = cv2.getTextSize(
            text, GUIDE_FONT, GUIDE_SCALE, GUIDE_THICKNESS
        )
        x = max((width - text_width) // 2, 0)
        y = height - GUIDE_MARGIN_PX
        cv2.rectangle(
            image,
            (x - GUIDE_BOX_PADDING_PX, y - text_height - GUIDE_BOX_PADDING_PX),
            (x + text_width + GUIDE_BOX_PADDING_PX, y + GUIDE_BOX_PADDING_PX),
            SURFACE_COLOR_BGR,
            GUIDE_BOX_THICKNESS,
        )
        cv2.putText(image, text, (x, y), GUIDE_FONT, GUIDE_SCALE, color, GUIDE_THICKNESS)
