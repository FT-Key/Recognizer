"""Overlay del contador de personas: cajas con ID, linea de conteo y HUD."""

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.core.domain.detection import (
    MAX_NORMALIZED_COORDINATE,
    MIN_NORMALIZED_COORDINATE,
)
from recognizer.core.domain.tracking import CountingLine, LineAxis, TrackedDetection

BOX_COLOR_BGR = (0, 200, 0)
BOX_THICKNESS = 2
LABEL_FONT = cv2.FONT_HERSHEY_SIMPLEX
LABEL_SCALE = 0.6
LABEL_THICKNESS = 1
LABEL_MARGIN_PX = 6
LABEL_TEMPLATE = "#{track_id} {label} {confidence:.2f}"
LINE_COLOR_BGR = (0, 215, 255)
LINE_THICKNESS = 2
LINE_MARGIN_COLOR_BGR = (0, 120, 140)
LINE_MARGIN_THICKNESS = 1
HUD_FONT = cv2.FONT_HERSHEY_SIMPLEX
HUD_SCALE = 0.9
HUD_THICKNESS = 2
HUD_COLOR_BGR = (0, 200, 0)
HUD_CURRENT_POSITION = (10, 30)
HUD_COUNTS_POSITION = (10, 60)
HUD_CURRENT_TEMPLATE = "Personas: {current}"
HUD_COUNTS_TEMPLATE = "Entradas: {entries}  Salidas: {exits}"


def _clamp_unit(value: float) -> float:
    """Recorta una coordenada normalizada al rango 0..1."""
    return max(MIN_NORMALIZED_COORDINATE, min(MAX_NORMALIZED_COORDINATE, value))


def _draw_line(
    image: NDArray[np.uint8],
    *,
    line: CountingLine,
    width: int,
    height: int,
) -> None:
    lower = _clamp_unit(line.position - line.margin)
    upper = _clamp_unit(line.position + line.margin)
    if line.axis is LineAxis.HORIZONTAL:
        y = int(line.position * height)
        cv2.line(image, (0, y), (width, y), LINE_COLOR_BGR, LINE_THICKNESS)
        if line.margin > MIN_NORMALIZED_COORDINATE:
            for offset in (lower, upper):
                y_margin = int(offset * height)
                cv2.line(
                    image,
                    (0, y_margin),
                    (width, y_margin),
                    LINE_MARGIN_COLOR_BGR,
                    LINE_MARGIN_THICKNESS,
                )
    else:
        x = int(line.position * width)
        cv2.line(image, (x, 0), (x, height), LINE_COLOR_BGR, LINE_THICKNESS)
        if line.margin > MIN_NORMALIZED_COORDINATE:
            for offset in (lower, upper):
                x_margin = int(offset * width)
                cv2.line(
                    image,
                    (x_margin, 0),
                    (x_margin, height),
                    LINE_MARGIN_COLOR_BGR,
                    LINE_MARGIN_THICKNESS,
                )


def _draw_tracked(
    image: NDArray[np.uint8],
    *,
    tracked: tuple[TrackedDetection, ...],
    width: int,
    height: int,
) -> None:
    for item in tracked:
        x_min = int(item.bbox.x_min * width)
        y_min = int(item.bbox.y_min * height)
        x_max = int(item.bbox.x_max * width)
        y_max = int(item.bbox.y_max * height)
        cv2.rectangle(image, (x_min, y_min), (x_max, y_max), BOX_COLOR_BGR, BOX_THICKNESS)
        label = LABEL_TEMPLATE.format(
            track_id=item.track_id,
            label=item.label,
            confidence=item.confidence,
        )
        cv2.putText(
            image,
            label,
            (x_min, max(y_min - LABEL_MARGIN_PX, 0)),
            LABEL_FONT,
            LABEL_SCALE,
            BOX_COLOR_BGR,
            LABEL_THICKNESS,
        )


def draw_people_overlay(
    image: NDArray[np.uint8],
    *,
    tracked: tuple[TrackedDetection, ...],
    current: int,
    entries: int,
    exits: int,
    line: CountingLine | None,
) -> None:
    """Dibuja cajas con ID, la linea de conteo y el HUD sobre el fotograma."""
    height, width = image.shape[:2]
    if line is not None:
        _draw_line(image, line=line, width=width, height=height)
    _draw_tracked(image, tracked=tracked, width=width, height=height)
    cv2.putText(
        image,
        HUD_CURRENT_TEMPLATE.format(current=current),
        HUD_CURRENT_POSITION,
        HUD_FONT,
        HUD_SCALE,
        HUD_COLOR_BGR,
        HUD_THICKNESS,
    )
    cv2.putText(
        image,
        HUD_COUNTS_TEMPLATE.format(entries=entries, exits=exits),
        HUD_COUNTS_POSITION,
        HUD_FONT,
        HUD_SCALE,
        HUD_COLOR_BGR,
        HUD_THICKNESS,
    )
