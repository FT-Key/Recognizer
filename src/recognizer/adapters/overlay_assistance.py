"""Overlay de asistencia: brazos, HUD y banner de pedido de ayuda."""

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.core.domain.pose import Pose, PoseKeypoint

ARM_COLOR_BGR = (0, 200, 0)
ARM_RAISED_COLOR_BGR = (0, 200, 255)
KEYPOINT_RADIUS_PX = 4
ARM_THICKNESS = 2
HUD_FONT = cv2.FONT_HERSHEY_SIMPLEX
HUD_SCALE = 0.8
HUD_THICKNESS = 2
HUD_COLOR_BGR = (0, 200, 0)
HUD_ACTIVE_COLOR_BGR = (0, 0, 255)
HUD_POSITION = (10, 30)
HUD_OK_TEXT = "Asistencia: OK"
HUD_ACTIVE_TEMPLATE = "Asistencia: ACTIVA ({count})"
BANNER_FONT = cv2.FONT_HERSHEY_SIMPLEX
BANNER_SCALE = 0.9
BANNER_THICKNESS = 2
BANNER_COLOR_BGR = (0, 0, 255)
BANNER_TEXT = "PEDIDO DE ASISTENCIA: brazos levantados"
BANNER_MARGIN_PX = 20

# Segmentos por brazo: hombro-codo-muneca de cada lado.
ARM_EDGES: tuple[tuple[PoseKeypoint, PoseKeypoint], ...] = (
    (PoseKeypoint.LEFT_SHOULDER, PoseKeypoint.LEFT_ELBOW),
    (PoseKeypoint.LEFT_ELBOW, PoseKeypoint.LEFT_WRIST),
    (PoseKeypoint.RIGHT_SHOULDER, PoseKeypoint.RIGHT_ELBOW),
    (PoseKeypoint.RIGHT_ELBOW, PoseKeypoint.RIGHT_WRIST),
    (PoseKeypoint.LEFT_SHOULDER, PoseKeypoint.RIGHT_SHOULDER),
)

# Lados (hombro, muneca) para resaltar el brazo levantado.
_ARM_SIDES: tuple[tuple[PoseKeypoint, PoseKeypoint], ...] = (
    (PoseKeypoint.LEFT_SHOULDER, PoseKeypoint.LEFT_WRIST),
    (PoseKeypoint.RIGHT_SHOULDER, PoseKeypoint.RIGHT_WRIST),
)


def _raised_sides(
    pose: Pose,
    *,
    min_keypoint_confidence: float,
    raise_margin: float,
) -> set[PoseKeypoint]:
    """Hombros con la muneca por encima (brazo levantado de ese lado)."""
    sides: set[PoseKeypoint] = set()
    for shoulder_name, wrist_name in _ARM_SIDES:
        shoulder = pose.keypoint(shoulder_name)
        wrist = pose.keypoint(wrist_name)
        if shoulder is None or wrist is None:
            continue
        if (
            shoulder.confidence < min_keypoint_confidence
            or wrist.confidence < min_keypoint_confidence
        ):
            continue
        if wrist.y + raise_margin < shoulder.y:
            sides.add(shoulder_name)
    return sides


def _draw_arms(
    image: NDArray[np.uint8],
    *,
    pose: Pose,
    raised_sides: set[PoseKeypoint],
    width: int,
    height: int,
    min_keypoint_confidence: float,
) -> None:
    for start_name, end_name in ARM_EDGES:
        start = pose.keypoint(start_name)
        end = pose.keypoint(end_name)
        if start is None or end is None:
            continue
        if start.confidence < min_keypoint_confidence or end.confidence < min_keypoint_confidence:
            continue
        raised = start_name in raised_sides or end_name in raised_sides
        color = ARM_RAISED_COLOR_BGR if raised else ARM_COLOR_BGR
        cv2.line(
            image,
            (int(start.x * width), int(start.y * height)),
            (int(end.x * width), int(end.y * height)),
            color,
            ARM_THICKNESS,
        )
    for keypoint in pose.keypoints:
        if keypoint.confidence < min_keypoint_confidence:
            continue
        if keypoint.name not in {
            PoseKeypoint.LEFT_SHOULDER,
            PoseKeypoint.RIGHT_SHOULDER,
            PoseKeypoint.LEFT_ELBOW,
            PoseKeypoint.RIGHT_ELBOW,
            PoseKeypoint.LEFT_WRIST,
            PoseKeypoint.RIGHT_WRIST,
        }:
            continue
        cv2.circle(
            image,
            (int(keypoint.x * width), int(keypoint.y * height)),
            KEYPOINT_RADIUS_PX,
            ARM_RAISED_COLOR_BGR if keypoint.name in raised_sides else ARM_COLOR_BGR,
            -1,
        )


def draw_assistance_overlay(
    image: NDArray[np.uint8],
    *,
    poses: tuple[Pose, ...],
    active: bool,
    raised: tuple[int, ...],
    min_keypoint_confidence: float,
    raise_margin: float,
) -> None:
    """Dibuja los brazos de cada persona, el HUD y el banner si hay pedido."""
    height, width = image.shape[:2]
    for pose in poses:
        _draw_arms(
            image,
            pose=pose,
            raised_sides=_raised_sides(
                pose,
                min_keypoint_confidence=min_keypoint_confidence,
                raise_margin=raise_margin,
            ),
            width=width,
            height=height,
            min_keypoint_confidence=min_keypoint_confidence,
        )

    if active:
        cv2.putText(
            image,
            HUD_ACTIVE_TEMPLATE.format(count=len(raised)),
            HUD_POSITION,
            HUD_FONT,
            HUD_SCALE,
            HUD_ACTIVE_COLOR_BGR,
            HUD_THICKNESS,
        )
        cv2.putText(
            image,
            BANNER_TEXT,
            (HUD_POSITION[0], height - BANNER_MARGIN_PX),
            BANNER_FONT,
            BANNER_SCALE,
            BANNER_COLOR_BGR,
            BANNER_THICKNESS,
        )
        return

    cv2.putText(
        image,
        HUD_OK_TEXT,
        HUD_POSITION,
        HUD_FONT,
        HUD_SCALE,
        HUD_COLOR_BGR,
        HUD_THICKNESS,
    )
