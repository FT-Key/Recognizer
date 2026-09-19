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
TARGET_FRAME_LABEL = "llena este marco"
TARGET_LABEL_MARGIN_PX = 6


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


def _draw_target_frame(
    image: NDArray[np.uint8],
    *,
    width: int,
    height: int,
    target_width_ratio: float,
    color: tuple[int, int, int],
) -> None:
    """Marco objetivo: cuadrado centrado donde debe encajar la cara.

    El lado equivale a ``target_width_ratio * width`` (el mismo umbral que
    exige ``assess_capture``): si la cara llena este marco, el enrolamiento
    la acepta. Sin etiqueta decorativa adicional salvo su instruccion.
    """
    side = int(width * target_width_ratio)
    if side <= 0:
        return
    x_min = max((width - side) // 2, 0)
    y_min = max((height - side) // 2, 0)
    x_max = min(x_min + side, width)
    y_max = min(y_min + side, height)
    cv2.rectangle(
        image,
        (x_min, y_min),
        (x_max, y_max),
        color,
        GUIDE_BOX_THICKNESS,
    )
    cv2.putText(
        image,
        TARGET_FRAME_LABEL,
        (x_min, max(y_min - TARGET_LABEL_MARGIN_PX, 0)),
        LABEL_FONT,
        LABEL_SCALE,
        color,
        LABEL_THICKNESS,
    )


def draw_face_overlay(
    image: NDArray[np.uint8],
    *,
    boxes: tuple[FaceBox, ...],
    guidance: CaptureGuidance | None,
    progress_text: str,
    login_text: str,
    highlight_ok: bool,
    target_width_ratio: float | None = None,
) -> None:
    """Dibuja cajas faciales, HUD superior (login + progreso) y guia inferior.

    Con ``target_width_ratio`` dibuja el marco objetivo (cuadrado centrado de
    lado ``target_width_ratio * W``); con ``None`` no dibuja ningun marco.
    """
    height, width = image.shape[:2]
    color = _guidance_color(guidance, highlight_ok=highlight_ok)
    if target_width_ratio is not None:
        _draw_target_frame(
            image,
            width=width,
            height=height,
            target_width_ratio=target_width_ratio,
            color=SURFACE_COLOR_BGR,
        )
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
