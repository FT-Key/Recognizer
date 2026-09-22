"""Overlay de caidas: esqueleto, HUD y banner de alerta."""

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.core.domain.pose import Pose, PoseKeypoint

BODY_COLOR_BGR = (200, 200, 200)
FALLEN_COLOR_BGR = (0, 0, 255)
KEYPOINT_RADIUS_PX = 4
BODY_THICKNESS = 2
HUD_FONT = cv2.FONT_HERSHEY_SIMPLEX
HUD_SCALE = 0.8
HUD_THICKNESS = 2
HUD_COLOR_BGR = (0, 200, 0)
HUD_ACTIVE_COLOR_BGR = (0, 0, 255)
HUD_POSITION = (10, 30)
HUD_OK_TEXT = "Caidas: OK"
HUD_ACTIVE_TEMPLATE = "Caidas: ALERTA ({count})"
BANNER_FONT = cv2.FONT_HERSHEY_SIMPLEX
BANNER_SCALE = 0.9
BANNER_THICKNESS = 2
BANNER_COLOR_BGR = (0, 0, 255)
BANNER_TEXT = "CAIDA DETECTADA"
BANNER_MARGIN_PX = 20

# Segmentos del cuerpo: hombros, torso, brazos, piernas.
BODY_EDGES: tuple[tuple[PoseKeypoint, PoseKeypoint], ...] = (
    (PoseKeypoint.LEFT_SHOULDER, PoseKeypoint.RIGHT_SHOULDER),
    (PoseKeypoint.LEFT_SHOULDER, PoseKeypoint.LEFT_ELBOW),
    (PoseKeypoint.LEFT_ELBOW, PoseKeypoint.LEFT_WRIST),
    (PoseKeypoint.RIGHT_SHOULDER, PoseKeypoint.RIGHT_ELBOW),
    (PoseKeypoint.RIGHT_ELBOW, PoseKeypoint.RIGHT_WRIST),
    (PoseKeypoint.LEFT_SHOULDER, PoseKeypoint.LEFT_HIP),
    (PoseKeypoint.RIGHT_SHOULDER, PoseKeypoint.RIGHT_HIP),
    (PoseKeypoint.LEFT_HIP, PoseKeypoint.RIGHT_HIP),
    (PoseKeypoint.LEFT_HIP, PoseKeypoint.LEFT_KNEE),
    (PoseKeypoint.LEFT_KNEE, PoseKeypoint.LEFT_ANKLE),
    (PoseKeypoint.RIGHT_HIP, PoseKeypoint.RIGHT_KNEE),
    (PoseKeypoint.RIGHT_KNEE, PoseKeypoint.RIGHT_ANKLE),
)

BODY_KEYPOINTS = {
    PoseKeypoint.LEFT_SHOULDER,
    PoseKeypoint.RIGHT_SHOULDER,
    PoseKeypoint.LEFT_ELBOW,
    PoseKeypoint.RIGHT_ELBOW,
    PoseKeypoint.LEFT_WRIST,
    PoseKeypoint.RIGHT_WRIST,
    PoseKeypoint.LEFT_HIP,
    PoseKeypoint.RIGHT_HIP,
    PoseKeypoint.LEFT_KNEE,
    PoseKeypoint.RIGHT_KNEE,
    PoseKeypoint.LEFT_ANKLE,
    PoseKeypoint.RIGHT_ANKLE,
}


def _draw_body(
    image: NDArray[np.uint8],
    *,
    pose: Pose,
    fallen: bool,
    width: int,
    height: int,
    min_keypoint_confidence: float,
) -> None:
    color = FALLEN_COLOR_BGR if fallen else BODY_COLOR_BGR
    for start_name, end_name in BODY_EDGES:
        start = pose.keypoint(start_name)
        end = pose.keypoint(end_name)
        if start is None or end is None:
            continue
        if start.confidence < min_keypoint_confidence or end.confidence < min_keypoint_confidence:
            continue
        cv2.line(
            image,
            (int(start.x * width), int(start.y * height)),
            (int(end.x * width), int(end.y * height)),
            color,
            BODY_THICKNESS,
        )
    for keypoint in pose.keypoints:
        if keypoint.confidence < min_keypoint_confidence:
            continue
        if keypoint.name not in BODY_KEYPOINTS:
            continue
        cv2.circle(
            image,
            (int(keypoint.x * width), int(keypoint.y * height)),
            KEYPOINT_RADIUS_PX,
            color,
            -1,
        )


def draw_fall_overlay(
    image: NDArray[np.uint8],
    *,
    poses: tuple[Pose, ...],
    active: bool,
    fallen: tuple[int, ...],
    min_keypoint_confidence: float,
) -> None:
    """Dibuja el esqueleto de cada persona, el HUD y el banner si hay caida."""
    height, width = image.shape[:2]
    for index, pose in enumerate(poses):
        _draw_body(
            image,
            pose=pose,
            fallen=index in fallen,
            width=width,
            height=height,
            min_keypoint_confidence=min_keypoint_confidence,
        )

    if active:
        cv2.putText(
            image,
            HUD_ACTIVE_TEMPLATE.format(count=len(fallen)),
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
