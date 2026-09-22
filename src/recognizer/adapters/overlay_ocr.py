"""Overlay de OCR: ROI, cajas de texto y HUD con resultados."""

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.core.domain.ocr import ROI, OCRBox

ROI_COLOR_BGR = (255, 255, 0)
ROI_THICKNESS = 2
BOX_COLOR_BGR = (0, 255, 0)
BOX_THICKNESS = 1
TEXT_FONT = cv2.FONT_HERSHEY_SIMPLEX
TEXT_SCALE = 0.5
TEXT_THICKNESS = 1
TEXT_COLOR_BGR = (0, 255, 0)
HUD_FONT = cv2.FONT_HERSHEY_SIMPLEX
HUD_SCALE = 0.7
HUD_THICKNESS = 2
HUD_COLOR_BGR = (0, 200, 0)
HUD_POSITION = (10, 30)
HUD_LINE_HEIGHT = 22


def draw_ocr_overlay(
    image: NDArray[np.uint8],
    *,
    boxes: tuple[OCRBox, ...],
    roi: ROI,
    texts: tuple[str, ...],
) -> None:
    """Dibuja la ROI, las cajas de texto detectadas y el HUD."""
    height, width = image.shape[:2]

    x1, y1, x2, y2 = roi.pixel_rect(width, height)
    cv2.rectangle(image, (x1, y1), (x2, y2), ROI_COLOR_BGR, ROI_THICKNESS)

    for box in boxes:
        cv2.rectangle(
            image,
            (box.x_min, box.y_min),
            (box.x_max, box.y_max),
            BOX_COLOR_BGR,
            BOX_THICKNESS,
        )
        label = f"{box.text} ({box.confidence:.0%})"
        cv2.putText(
            image,
            label,
            (box.x_min, box.y_min - 5),
            TEXT_FONT,
            TEXT_SCALE,
            TEXT_COLOR_BGR,
            TEXT_THICKNESS,
        )

    y_offset = HUD_POSITION[1]
    cv2.putText(
        image,
        f"OCR: {len(texts)} textos",
        HUD_POSITION,
        HUD_FONT,
        HUD_SCALE,
        HUD_COLOR_BGR,
        HUD_THICKNESS,
    )
    y_offset += HUD_LINE_HEIGHT
    for text in texts[:5]:
        cv2.putText(
            image,
            text[:60],
            (HUD_POSITION[0], y_offset),
            HUD_FONT,
            0.5,
            HUD_COLOR_BGR,
            1,
        )
        y_offset += HUD_LINE_HEIGHT
