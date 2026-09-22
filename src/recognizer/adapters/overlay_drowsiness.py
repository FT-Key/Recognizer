"""Overlay de somnolencia: esqueleto, metricas faciales y banner de alerta."""

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.core.domain.pose import Pose, PoseKeypoint

BODY_COLOR_BGR = (200, 200, 200)
DROWSY_COLOR_BGR = (0, 165, 255)
KEYPOINT_RADIUS_PX = 4
BODY_THICKNESS = 2
HUD_FONT = cv2.FONT_HERSHEY_SIMPLEX
HUD_SCALE = 0.8
HUD_THICKNESS = 2
HUD_COLOR_BGR = (0, 200, 0)
HUD_ACTIVE_COLOR_BGR = (0, 165, 255)
HUD_POSITION = (10, 30)
HUD_OK_TEXT = "Somnolencia: OK"
HUD_ACTIVE_TEMPLATE = "Somnolencia: ALERTA ({count})"
BANNER_FONT = cv2.FONT_HERSHEY_SIMPLEX
BANNER_SCALE = 0.9
BANNER_THICKNESS = 2
BANNER_COLOR_BGR = (0, 165, 255)
BANNER_TEXT = "SOMNOLENCIA DETECTADA"
BANNER_MARGIN_PX = 20
# Metricas faciales
METRICS_FONT = cv2.FONT_HERSHEY_SIMPLEX
METRICS_SCALE = 0.6
METRICS_THICKNESS = 1
METRICS_COLOR_BGR = (255, 255, 0)
METRICS_POSITION = (10, 60)
METRICS_LINE_HEIGHT = 22

FACE_EDGES: tuple[tuple[PoseKeypoint, PoseKeypoint], ...] = (
    (PoseKeypoint.LEFT_EYE, PoseKeypoint.NOSE),
    (PoseKeypoint.RIGHT_EYE, PoseKeypoint.NOSE),
    (PoseKeypoint.LEFT_EAR, PoseKeypoint.LEFT_EYE),
    (PoseKeypoint.RIGHT_EAR, PoseKeypoint.RIGHT_EYE),
)

BODY_EDGES: tuple[tuple[PoseKeypoint, PoseKeypoint], ...] = (
    (PoseKeypoint.LEFT_SHOULDER, PoseKeypoint.RIGHT_SHOULDER),
    (PoseKeypoint.LEFT_SHOULDER, PoseKeypoint.LEFT_ELBOW),
    (PoseKeypoint.LEFT_ELBOW, PoseKeypoint.LEFT_WRIST),
    (PoseKeypoint.RIGHT_SHOULDER, PoseKeypoint.RIGHT_ELBOW),
    (PoseKeypoint.RIGHT_ELBOW, PoseKeypoint.RIGHT_WRIST),
    (PoseKeypoint.LEFT_SHOULDER, PoseKeypoint.LEFT_HIP),
    (PoseKeypoint.RIGHT_SHOULDER, PoseKeypoint.RIGHT_HIP),
    (PoseKeypoint.LEFT_HIP, PoseKeypoint.RIGHT_HIP),
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
}

FACE_KEYPOINTS = {
    PoseKeypoint.NOSE,
    PoseKeypoint.LEFT_EYE,
    PoseKeypoint.RIGHT_EYE,
    PoseKeypoint.LEFT_EAR,
    PoseKeypoint.RIGHT_EAR,
}


def _draw_skeleton(
    image: NDArray[np.uint8],
    *,
    pose: Pose,
    drowsy: bool,
    width: int,
    height: int,
    min_keypoint_confidence: float,
) -> None:
    color = DROWSY_COLOR_BGR if drowsy else BODY_COLOR_BGR
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
        if keypoint.name in BODY_KEYPOINTS or keypoint.name in FACE_KEYPOINTS:
            cv2.circle(
                image,
                (int(keypoint.x * width), int(keypoint.y * height)),
                KEYPOINT_RADIUS_PX,
                color,
                -1,
            )


def _draw_metrics(
    image: NDArray[np.uint8],
    *,
    ear_avg: float | None,
    mar: float | None,
    head_droop: float | None,
    nod_amplitude: float | None,
) -> None:
    """Dibuja las metricas faciales en el overlay."""
    y_offset = METRICS_POSITION[1]
    lines: list[str] = []
    if ear_avg is not None:
        lines.append(f"EAR: {ear_avg:.3f}")
    if mar is not None:
        lines.append(f"MAR: {mar:.3f}")
    if head_droop is not None:
        lines.append(f"Cabeza: {head_droop:.3f}")
    if nod_amplitude is not None:
        lines.append(f"Cabeceo: {nod_amplitude:.3f}")
    for line in lines:
        cv2.putText(
            image,
            line,
            (METRICS_POSITION[0], y_offset),
            METRICS_FONT,
            METRICS_SCALE,
            METRICS_COLOR_BGR,
            METRICS_THICKNESS,
        )
        y_offset += METRICS_LINE_HEIGHT


def draw_drowsiness_overlay(
    image: NDArray[np.uint8],
    *,
    poses: tuple[Pose, ...],
    active: bool,
    drowsy_count: int,
    min_keypoint_confidence: float,
    ear_avg: float | None = None,
    mar: float | None = None,
    head_droop: float | None = None,
    nod_amplitude: float | None = None,
) -> None:
    """Dibuja el esqueleto de cada persona, metricas faciales, HUD y banner."""
    height, width = image.shape[:2]
    for pose in poses:
        _draw_skeleton(
            image,
            pose=pose,
            drowsy=active,
            width=width,
            height=height,
            min_keypoint_confidence=min_keypoint_confidence,
        )

    _draw_metrics(
        image,
        ear_avg=ear_avg,
        mar=mar,
        head_droop=head_droop,
        nod_amplitude=nod_amplitude,
    )

    if active:
        cv2.putText(
            image,
            HUD_ACTIVE_TEMPLATE.format(count=drowsy_count),
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
