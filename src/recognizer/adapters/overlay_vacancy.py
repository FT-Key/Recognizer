"""Overlay de vacancy: indicador de presencia/ausencia y banner de alerta."""

import cv2
import numpy as np
from numpy.typing import NDArray

HUD_FONT = cv2.FONT_HERSHEY_SIMPLEX
HUD_SCALE = 0.9
HUD_THICKNESS = 2
HUD_PRESENT_COLOR_BGR = (0, 200, 0)
HUD_ABSENT_COLOR_BGR = (0, 0, 255)
HUD_POSITION = (10, 30)
HUD_TEMPLATE = "Personas: {count} | Ausencia: {empty_sec:.1f}s"
ALERT_FONT = cv2.FONT_HERSHEY_SIMPLEX
ALERT_SCALE = 0.9
ALERT_THICKNESS = 2
ALERT_COLOR_BGR = (0, 0, 255)
ALERT_TEXT = "ALERTA: ZONA VACIA - SIN PRESENCIA"
ALERT_MARGIN_PX = 20


def draw_vacancy_overlay(
    image: NDArray[np.uint8],
    *,
    people_count: int,
    active: bool,
    empty_seconds: float,
) -> None:
    """Dibuja el HUD con conteo de personas y el banner de alerta si aplica."""
    height, _width = image.shape[:2]
    color = HUD_PRESENT_COLOR_BGR if not active else HUD_ABSENT_COLOR_BGR
    cv2.putText(
        image,
        HUD_TEMPLATE.format(count=people_count, empty_sec=empty_seconds),
        HUD_POSITION,
        HUD_FONT,
        HUD_SCALE,
        color,
        HUD_THICKNESS,
    )
    if active:
        cv2.putText(
            image,
            ALERT_TEXT,
            (HUD_POSITION[0], height - ALERT_MARGIN_PX),
            ALERT_FONT,
            ALERT_SCALE,
            ALERT_COLOR_BGR,
            ALERT_THICKNESS,
        )
