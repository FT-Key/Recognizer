"""Overlay facial estilo vintage: cajas, HUD superior y guia inferior.

El texto se dibuja sobre paneles oscuros con borde de color para garantizar
contraste sobre cualquier fotograma (antes era gris sobre video y no se leia).
"""

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.core.domain.face import CaptureGuidance, FaceBox

SUCCESS_COLOR_BGR = (0, 200, 0)
WARNING_COLOR_BGR = (0, 165, 255)
DANGER_COLOR_BGR = (0, 0, 255)
SURFACE_COLOR_BGR = (180, 180, 180)
PANEL_COLOR_BGR = (20, 20, 20)
TEXT_COLOR_BGR = (255, 255, 255)
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
HUD_PANEL_ORIGIN = (10, 8)
PROGRESS_PANEL_ORIGIN = (10, 52)
GUIDE_FONT = cv2.FONT_HERSHEY_SIMPLEX
GUIDE_SCALE = 0.8
GUIDE_THICKNESS = 2
GUIDE_MARGIN_PX = 16
PANEL_PADDING_PX = 8
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


def _panel_size(*, text: str, font: int, scale: float, thickness: int) -> tuple[int, int]:
    """Ancho y alto del panel que contiene ``text`` con padding."""
    (text_width, text_height), _ = cv2.getTextSize(text, font, scale, thickness)
    return text_width + 2 * PANEL_PADDING_PX, text_height + 2 * PANEL_PADDING_PX


def _draw_panel_text(
    image: NDArray[np.uint8],
    *,
    text: str,
    origin: tuple[int, int],
    font: int,
    scale: float,
    thickness: int,
    text_color: tuple[int, int, int],
    border_color: tuple[int, int, int],
) -> None:
    """Dibuja texto legible sobre un panel oscuro con borde de color.

    ``origin`` es la esquina superior izquierda del panel.
    """
    panel_width, panel_height = _panel_size(text=text, font=font, scale=scale, thickness=thickness)
    x, y = origin
    x_max = x + panel_width
    y_max = y + panel_height
    cv2.rectangle(image, (x, y), (x_max, y_max), PANEL_COLOR_BGR, cv2.FILLED)
    cv2.rectangle(image, (x, y), (x_max, y_max), border_color, GUIDE_BOX_THICKNESS)
    cv2.putText(
        image,
        text,
        (x + PANEL_PADDING_PX, y + panel_height - PANEL_PADDING_PX),
        font,
        scale,
        text_color,
        thickness,
    )


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
        _draw_panel_text(
            image,
            text=LABEL_TEMPLATE.format(confidence=box.confidence),
            origin=(x_min, max(y_min - LABEL_MARGIN_PX - 24, 0)),
            font=LABEL_FONT,
            scale=LABEL_SCALE,
            thickness=LABEL_THICKNESS,
            text_color=TEXT_COLOR_BGR,
            border_color=color,
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
    la acepta.
    """
    side = int(width * target_width_ratio)
    if side <= 0:
        return
    x_min = max((width - side) // 2, 0)
    y_min = max((height - side) // 2, 0)
    x_max = min(x_min + side, width)
    y_max = min(y_min + side, height)
    cv2.rectangle(image, (x_min, y_min), (x_max, y_max), color, GUIDE_BOX_THICKNESS)
    _draw_panel_text(
        image,
        text=TARGET_FRAME_LABEL,
        origin=(x_min, max(y_min - TARGET_LABEL_MARGIN_PX - 24, 0)),
        font=LABEL_FONT,
        scale=LABEL_SCALE,
        thickness=LABEL_THICKNESS,
        text_color=TEXT_COLOR_BGR,
        border_color=color,
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
        _draw_panel_text(
            image,
            text=login_text,
            origin=HUD_PANEL_ORIGIN,
            font=HUD_FONT,
            scale=HUD_SCALE,
            thickness=HUD_THICKNESS,
            text_color=SUCCESS_COLOR_BGR if highlight_ok else TEXT_COLOR_BGR,
            border_color=SUCCESS_COLOR_BGR if highlight_ok else WARNING_COLOR_BGR,
        )
    if progress_text:
        _draw_panel_text(
            image,
            text=progress_text,
            origin=PROGRESS_PANEL_ORIGIN,
            font=HUD_FONT,
            scale=HUD_SCALE,
            thickness=HUD_THICKNESS,
            text_color=TEXT_COLOR_BGR,
            border_color=SURFACE_COLOR_BGR,
        )
    if guidance is not None:
        text = guidance.value
        panel_width, panel_height = _panel_size(
            text=text, font=GUIDE_FONT, scale=GUIDE_SCALE, thickness=GUIDE_THICKNESS
        )
        x = max((width - panel_width) // 2, 0)
        y = max(height - panel_height - GUIDE_MARGIN_PX, 0)
        _draw_panel_text(
            image,
            text=text,
            origin=(x, y),
            font=GUIDE_FONT,
            scale=GUIDE_SCALE,
            thickness=GUIDE_THICKNESS,
            text_color=TEXT_COLOR_BGR,
            border_color=color,
        )
