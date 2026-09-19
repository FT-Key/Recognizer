"""Overlay del anti-intrusos: zona, cajas con ID, HUD y banner de alerta."""

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.core.domain.intrusion import IntrusionZone
from recognizer.core.domain.tracking import TrackedDetection

ZONE_OK_COLOR_BGR = (0, 200, 0)
ZONE_ALERT_COLOR_BGR = (0, 0, 255)
ZONE_THICKNESS = 2
BOX_COLOR_BGR = (0, 200, 0)
INTRUDER_BOX_COLOR_BGR = (0, 0, 255)
BOX_THICKNESS = 2
LABEL_FONT = cv2.FONT_HERSHEY_SIMPLEX
LABEL_SCALE = 0.6
LABEL_THICKNESS = 1
LABEL_MARGIN_PX = 6
LABEL_TEMPLATE = "#{track_id} {label} {confidence:.2f}"
HUD_FONT = cv2.FONT_HERSHEY_SIMPLEX
HUD_SCALE = 0.9
HUD_THICKNESS = 2
HUD_COLOR_BGR = (0, 200, 0)
HUD_POSITION = (10, 30)
HUD_TEMPLATE = "Zona: {count} intrusos"
ALERT_FONT = cv2.FONT_HERSHEY_SIMPLEX
ALERT_SCALE = 0.9
ALERT_THICKNESS = 2
ALERT_COLOR_BGR = (0, 0, 255)
ALERT_TEXT = "ALERTA: INTRUSO EN ZONA"
ALERT_MARGIN_PX = 20


def _draw_zone(
    image: NDArray[np.uint8],
    *,
    zone: IntrusionZone,
    active: bool,
    width: int,
    height: int,
) -> None:
    color = ZONE_ALERT_COLOR_BGR if active else ZONE_OK_COLOR_BGR
    top_left = (int(zone.x_min * width), int(zone.y_min * height))
    bottom_right = (int(zone.x_max * width), int(zone.y_max * height))
    cv2.rectangle(image, top_left, bottom_right, color, ZONE_THICKNESS)


def _draw_tracked(
    image: NDArray[np.uint8],
    *,
    tracked: tuple[TrackedDetection, ...],
    intruder_ids: frozenset[int],
    width: int,
    height: int,
) -> None:
    for item in tracked:
        color = INTRUDER_BOX_COLOR_BGR if item.track_id in intruder_ids else BOX_COLOR_BGR
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


def draw_intrusion_overlay(
    image: NDArray[np.uint8],
    *,
    tracked: tuple[TrackedDetection, ...],
    zone: IntrusionZone | None,
    active: bool,
    intruder_ids: frozenset[int],
) -> None:
    """Dibuja la zona, las cajas con ID, el HUD y el banner de alerta si aplica."""
    height, width = image.shape[:2]
    if zone is not None:
        _draw_zone(image, zone=zone, active=active, width=width, height=height)
    _draw_tracked(
        image,
        tracked=tracked,
        intruder_ids=intruder_ids,
        width=width,
        height=height,
    )
    cv2.putText(
        image,
        HUD_TEMPLATE.format(count=len(intruder_ids)),
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
