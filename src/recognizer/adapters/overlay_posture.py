"""Overlay de postura: esqueleto, HUD y banner de aviso."""

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.core.domain.pose import Pose, PoseKeypoint
from recognizer.core.domain.posture import PostureIssue

SKELETON_COLOR_BGR = (0, 200, 0)
SKELETON_BAD_COLOR_BGR = (0, 0, 255)
KEYPOINT_RADIUS_PX = 3
SKELETON_THICKNESS = 2
HUD_FONT = cv2.FONT_HERSHEY_SIMPLEX
HUD_SCALE = 0.8
HUD_THICKNESS = 2
HUD_COLOR_BGR = (0, 200, 0)
HUD_BAD_COLOR_BGR = (0, 0, 255)
HUD_POSITION = (10, 30)
HUD_OK_TEXT = "Postura: OK"
HUD_BAD_TEMPLATE = "Postura: {issues}"
BANNER_FONT = cv2.FONT_HERSHEY_SIMPLEX
BANNER_SCALE = 0.9
BANNER_THICKNESS = 2
BANNER_COLOR_BGR = (0, 0, 255)
BANNER_TEMPLATE = "MALA POSTURA: {issues}"
BANNER_MARGIN_PX = 20
ISSUE_SEPARATOR = ", "
CALIBRATION_COLOR_BGR = (0, 200, 255)
CALIBRATION_TEXT = "CALIBRANDO: sientate derecho"

# Conexiones del esqueleto COCO (pares de puntos clave).
SKELETON_EDGES: tuple[tuple[PoseKeypoint, PoseKeypoint], ...] = (
    (PoseKeypoint.NOSE, PoseKeypoint.LEFT_EYE),
    (PoseKeypoint.NOSE, PoseKeypoint.RIGHT_EYE),
    (PoseKeypoint.LEFT_EYE, PoseKeypoint.LEFT_EAR),
    (PoseKeypoint.RIGHT_EYE, PoseKeypoint.RIGHT_EAR),
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


def _draw_skeleton(
    image: NDArray[np.uint8],
    *,
    pose: Pose,
    color: tuple[int, int, int],
    width: int,
    height: int,
    min_keypoint_confidence: float,
) -> None:
    for start_name, end_name in SKELETON_EDGES:
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
            SKELETON_THICKNESS,
        )
    for keypoint in pose.keypoints:
        if keypoint.confidence < min_keypoint_confidence:
            continue
        cv2.circle(
            image,
            (int(keypoint.x * width), int(keypoint.y * height)),
            KEYPOINT_RADIUS_PX,
            color,
            -1,
        )


def _issues_text(issues: tuple[PostureIssue, ...]) -> str:
    return ISSUE_SEPARATOR.join(issue.value for issue in issues)


def draw_posture_overlay(
    image: NDArray[np.uint8],
    *,
    poses: tuple[Pose, ...],
    active: bool,
    issues: tuple[PostureIssue, ...],
    min_keypoint_confidence: float,
    calibrating: bool = False,
) -> None:
    """Dibuja el esqueleto de cada persona, el HUD y el banner si hay aviso."""
    height, width = image.shape[:2]
    color = SKELETON_BAD_COLOR_BGR if active else SKELETON_COLOR_BGR
    for pose in poses:
        _draw_skeleton(
            image,
            pose=pose,
            color=color,
            width=width,
            height=height,
            min_keypoint_confidence=min_keypoint_confidence,
        )

    if calibrating:
        cv2.putText(
            image,
            CALIBRATION_TEXT,
            HUD_POSITION,
            HUD_FONT,
            HUD_SCALE,
            CALIBRATION_COLOR_BGR,
            HUD_THICKNESS,
        )
        return

    if active:
        cv2.putText(
            image,
            HUD_BAD_TEMPLATE.format(issues=_issues_text(issues)),
            HUD_POSITION,
            HUD_FONT,
            HUD_SCALE,
            HUD_BAD_COLOR_BGR,
            HUD_THICKNESS,
        )
        cv2.putText(
            image,
            BANNER_TEMPLATE.format(issues=_issues_text(issues)),
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
