"""Overlay de loitering: zona, cajas con ID y tiempo, HUD y banner de alerta."""

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.core.domain.loitering import LoiteringZone
from recognizer.core.domain.tracking import TrackedDetection

ZONE_OK_COLOR_BGR = (0, 200, 0)
ZONE_ALERT_COLOR_BGR = (0, 0, 255)
ZONE_THICKNESS = 2
BOX_NORMAL_COLOR_BGR = (0, 200, 0)
BOX_WARN_COLOR_BGR = (0, 165, 255)
BOX_ALERT_COLOR_BGR = (0, 0, 255)
BOX_THICKNESS = 2
LABEL_FONT = cv2.FONT_HERSHEY_SIMPLEX
LABEL_SCALE = 0.6
LABEL_THICKNESS = 1
LABEL_MARGIN_PX = 6
LABEL_TEMPLATE = "#{track_id} {label} {confidence:.2f}"
DWELL_FONT = cv2.FONT_HERSHEY_SIMPLEX
DWELL_SCALE = 0.55
DWELL_THICKNESS = 1
DWELL_OK_COLOR_BGR = (0, 200, 0)
DWELL_WARN_COLOR_BGR = (0, 165, 255)
DWELL_ALERT_COLOR_BGR = (0, 0, 255)
HUD_FONT = cv2.FONT_HERSHEY_SIMPLEX
HUD_SCALE = 0.9
HUD_THICKNESS = 2
HUD_COLOR_BGR = (0, 200, 0)
HUD_POSITION = (10, 30)
HUD_TEMPLATE = "Permanencia: {count} alerta(s) | Max: {max_dwell:.1f}s"
ALERT_FONT = cv2.FONT_HERSHEY_SIMPLEX
ALERT_SCALE = 0.9
ALERT_THICKNESS = 2
ALERT_COLOR_BGR = (0, 0, 255)
ALERT_TEXT = "ALERTA: PERMANENCIA EXCEDIDA"
ALERT_MARGIN_PX = 20


def _draw_zone(
    image: NDArray[np.uint8],
    *,
    zone: LoiteringZone,
    active: bool,
    width: int,
    height: int,
) -> None:
    color = ZONE_ALERT_COLOR_BGR if active else ZONE_OK_COLOR_BGR
    top_left = (int(zone.x_min * width), int(zone.y_min * height))
    bottom_right = (int(zone.x_max * width), int(zone.y_max * height))
    cv2.rectangle(image, top_left, bottom_right, color, ZONE_THICKNESS)


def _dwell_color(dwell_sec: float, threshold: float) -> tuple[int, int, int]:
    if dwell_sec >= threshold:
        return DWELL_ALERT_COLOR_BGR
    if dwell_sec >= threshold * 0.7:
        return DWELL_WARN_COLOR_BGR
    return DWELL_OK_COLOR_BGR


def _draw_tracked(
    image: NDArray[np.uint8],
    *,
    tracked: tuple[TrackedDetection, ...],
    loiterer_ids: frozenset[int],
    dwell_times: dict[int, float],
    threshold: float,
    width: int,
    height: int,
) -> None:
    for item in tracked:
        if item.track_id in loiterer_ids:
            color = BOX_ALERT_COLOR_BGR
        elif item.track_id in dwell_times and dwell_times[item.track_id] >= threshold * 0.7:
            color = BOX_WARN_COLOR_BGR
        else:
            color = BOX_NORMAL_COLOR_BGR
        x_min = int(item.bbox.x_min * width)
        y_min = int(item.bbox.y_min * height)
        x_max = int(item.bbox.x_max * width)
        y_max = int(item.bbox.y_max * height)
        cv2.rectangle(image, (x_min, y_min), (x_max, y_max), color, BOX_THICKNESS)
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
            color,
            LABEL_THICKNESS,
        )
        if item.track_id in dwell_times:
            dwell_sec = dwell_times[item.track_id]
            dwell_color = _dwell_color(dwell_sec, threshold)
            dwell_text = f"{dwell_sec:.1f}s"
            cv2.putText(
                image,
                dwell_text,
                (x_min, min(y_max + 15, height - 5)),
                DWELL_FONT,
                DWELL_SCALE,
                dwell_color,
                DWELL_THICKNESS,
            )


def draw_loitering_overlay(
    image: NDArray[np.uint8],
    *,
    tracked: tuple[TrackedDetection, ...],
    zone: LoiteringZone | None,
    active: bool,
    loiterer_ids: frozenset[int],
    dwell_times: dict[int, float],
    threshold: float,
) -> None:
    """Dibuja la zona, las cajas con dwell, el HUD y el banner de alerta si aplica."""
    height, width = image.shape[:2]
    if zone is not None:
        _draw_zone(image, zone=zone, active=active, width=width, height=height)
    _draw_tracked(
        image,
        tracked=tracked,
        loiterer_ids=loiterer_ids,
        dwell_times=dwell_times,
        threshold=threshold,
        width=width,
        height=height,
    )
    max_dwell = max(dwell_times.values()) if dwell_times else 0.0
    cv2.putText(
        image,
        HUD_TEMPLATE.format(count=len(loiterer_ids), max_dwell=max_dwell),
        HUD_POSITION,
        HUD_FONT,
        HUD_SCALE,
        HUD_COLOR_BGR,
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
