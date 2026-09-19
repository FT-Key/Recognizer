"""Evaluacion de postura ergonomica (dominio puro).

A partir de los puntos clave de ``Pose`` se detectan malos habitos posturales
frente a la camara: cabeza adelantada, cabeza baja, espalda inclinada y hombros
desnivelados. ``PostureMonitor`` aplica un debounce: exige ``confirm_frames``
fotogramas consecutivos con mala postura para activar el aviso y ``release_frames``
fotogramas correctos (o sin persona evaluable) para retirarlo.
"""

import math
from dataclasses import dataclass
from enum import StrEnum

from recognizer.core.constants import (
    DEFAULT_POSTURE_CONFIRM_FRAMES,
    DEFAULT_POSTURE_MAX_HEAD_OFFSET_RATIO,
    DEFAULT_POSTURE_MAX_SHOULDER_TILT_RATIO,
    DEFAULT_POSTURE_MAX_TORSO_ANGLE_DEG,
    DEFAULT_POSTURE_MIN_HEAD_HEIGHT_RATIO,
    DEFAULT_POSTURE_RELEASE_FRAMES,
    MIN_VECTOR_NORM,
)
from recognizer.core.domain.pose import Pose, PoseKeypoint
from recognizer.core.errors import ConfigError


class PostureIssue(StrEnum):
    """Habito postural incorrecto detectado."""

    HEAD_FORWARD = "cabeza adelante"
    HEAD_DROP = "cabeza baja"
    TORSO_LEAN = "espalda inclinada"
    SHOULDER_TILT = "hombros desnivelados"


@dataclass(frozen=True, slots=True)
class PostureThresholds:
    """Umbrales normalizados (respecto al ancho de hombros) de la evaluacion."""

    max_head_offset_ratio: float = DEFAULT_POSTURE_MAX_HEAD_OFFSET_RATIO
    min_head_height_ratio: float = DEFAULT_POSTURE_MIN_HEAD_HEIGHT_RATIO
    max_torso_angle_deg: float = DEFAULT_POSTURE_MAX_TORSO_ANGLE_DEG
    max_shoulder_tilt_ratio: float = DEFAULT_POSTURE_MAX_SHOULDER_TILT_RATIO


@dataclass(frozen=True, slots=True)
class PostureAssessment:
    """Resultado de evaluar una postura en un fotograma."""

    evaluated: bool
    issues: tuple[PostureIssue, ...] = ()

    @property
    def is_bad(self) -> bool:
        """Indica si la postura evaluada tiene al menos un problema."""
        return bool(self.issues)


@dataclass(frozen=True, slots=True)
class PostureSnapshot:
    """Estado confirmado de la postura tras el debounce."""

    active: bool
    issues: tuple[PostureIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class _Landmarks:
    """Puntos clave relevantes ya resueltos para evaluar la postura."""

    nose: tuple[float, float]
    left_shoulder: tuple[float, float]
    right_shoulder: tuple[float, float]
    left_hip: tuple[float, float]
    right_hip: tuple[float, float]

    @property
    def shoulder_center(self) -> tuple[float, float]:
        """Centro entre ambos hombros."""
        return (
            (self.left_shoulder[0] + self.right_shoulder[0]) / 2,
            (self.left_shoulder[1] + self.right_shoulder[1]) / 2,
        )

    @property
    def hip_center(self) -> tuple[float, float]:
        """Centro entre ambas caderas."""
        return (
            (self.left_hip[0] + self.right_hip[0]) / 2,
            (self.left_hip[1] + self.right_hip[1]) / 2,
        )

    @property
    def shoulder_width(self) -> float:
        """Distancia entre hombros (normalizada); robusta a vista girada."""
        return math.dist(self.left_shoulder, self.right_shoulder)


def _resolve_landmarks(pose: Pose, *, min_keypoint_confidence: float) -> _Landmarks | None:
    """Extrae los puntos clave necesarios; ``None`` si falta alguno fiable."""
    required = (
        PoseKeypoint.NOSE,
        PoseKeypoint.LEFT_SHOULDER,
        PoseKeypoint.RIGHT_SHOULDER,
        PoseKeypoint.LEFT_HIP,
        PoseKeypoint.RIGHT_HIP,
    )
    points: dict[PoseKeypoint, tuple[float, float]] = {}
    for name in required:
        keypoint = pose.keypoint(name)
        if keypoint is None or keypoint.confidence < min_keypoint_confidence:
            return None
        points[name] = (keypoint.x, keypoint.y)
    return _Landmarks(
        nose=points[PoseKeypoint.NOSE],
        left_shoulder=points[PoseKeypoint.LEFT_SHOULDER],
        right_shoulder=points[PoseKeypoint.RIGHT_SHOULDER],
        left_hip=points[PoseKeypoint.LEFT_HIP],
        right_hip=points[PoseKeypoint.RIGHT_HIP],
    )


def assess_posture(
    pose: Pose,
    *,
    thresholds: PostureThresholds,
    min_keypoint_confidence: float,
) -> PostureAssessment:
    """Evalua una postura y devuelve los habitos incorrectos detectados."""
    landmarks = _resolve_landmarks(pose, min_keypoint_confidence=min_keypoint_confidence)
    if landmarks is None:
        return PostureAssessment(evaluated=False)
    width = landmarks.shoulder_width
    if width <= MIN_VECTOR_NORM:
        return PostureAssessment(evaluated=False)

    shoulder_x, shoulder_y = landmarks.shoulder_center
    hip_x, hip_y = landmarks.hip_center
    nose_x, nose_y = landmarks.nose

    issues: list[PostureIssue] = []
    if abs(nose_x - shoulder_x) / width > thresholds.max_head_offset_ratio:
        issues.append(PostureIssue.HEAD_FORWARD)
    if (shoulder_y - nose_y) / width < thresholds.min_head_height_ratio:
        issues.append(PostureIssue.HEAD_DROP)

    torso_angle = math.degrees(math.atan2(abs(hip_x - shoulder_x), hip_y - shoulder_y))
    if hip_y > shoulder_y and torso_angle > thresholds.max_torso_angle_deg:
        issues.append(PostureIssue.TORSO_LEAN)

    shoulder_tilt = abs(landmarks.left_shoulder[1] - landmarks.right_shoulder[1]) / width
    if shoulder_tilt > thresholds.max_shoulder_tilt_ratio:
        issues.append(PostureIssue.SHOULDER_TILT)

    return PostureAssessment(evaluated=True, issues=tuple(issues))


class PostureMonitor:
    """Confirma mala postura con debounce sobre la persona mas fiable."""

    def __init__(
        self,
        *,
        thresholds: PostureThresholds,
        min_keypoint_confidence: float,
        confirm_frames: int = DEFAULT_POSTURE_CONFIRM_FRAMES,
        release_frames: int = DEFAULT_POSTURE_RELEASE_FRAMES,
    ) -> None:
        if confirm_frames < 1:
            msg = f"La confirmacion requiere confirm_frames >= 1 (llego {confirm_frames})."
            raise ConfigError(msg)
        if release_frames < 1:
            msg = f"La liberacion requiere release_frames >= 1 (llego {release_frames})."
            raise ConfigError(msg)
        self._thresholds = thresholds
        self._min_keypoint_confidence = min_keypoint_confidence
        self._confirm_frames = confirm_frames
        self._release_frames = release_frames
        self._bad_frames = 0
        self._good_frames = 0
        self._missing_frames = 0
        self._active = False
        self._issues: tuple[PostureIssue, ...] = ()

    def update(self, poses: tuple[Pose, ...]) -> PostureSnapshot:
        """Actualiza el estado con las posturas del fotograma."""
        assessment = self._primary_assessment(poses)
        if assessment is None:
            self._on_missing()
        elif assessment.is_bad:
            self._on_bad(assessment.issues)
        else:
            self._on_good()
        return PostureSnapshot(active=self._active, issues=self._issues)

    def reset(self) -> None:
        """Limpia el estado del debounce."""
        self._bad_frames = 0
        self._good_frames = 0
        self._missing_frames = 0
        self._active = False
        self._issues = ()

    def _on_bad(self, issues: tuple[PostureIssue, ...]) -> None:
        self._bad_frames += 1
        self._good_frames = 0
        self._missing_frames = 0
        if self._bad_frames >= self._confirm_frames:
            self._active = True
            self._issues = issues

    def _on_good(self) -> None:
        self._good_frames += 1
        self._bad_frames = 0
        self._missing_frames = 0
        if self._good_frames >= self._release_frames:
            self._release()

    def _on_missing(self) -> None:
        """Un cuadro sin pose evaluable no rompe la racha de mala postura.

        Si la ausencia se prolonga ``release_frames`` cuadros se libera el aviso,
        para no dejar la alerta colgada cuando la persona sale del encuadre.
        """
        self._missing_frames += 1
        if self._missing_frames >= self._release_frames:
            self._release()

    def _release(self) -> None:
        self._active = False
        self._issues = ()
        self._bad_frames = 0
        self._good_frames = 0
        self._missing_frames = 0

    def _primary_assessment(self, poses: tuple[Pose, ...]) -> PostureAssessment | None:
        """Evalua la persona con mayor confianza; ``None`` si no hay evaluables."""
        best: PostureAssessment | None = None
        best_confidence = -1.0
        for pose in poses:
            assessment = assess_posture(
                pose,
                thresholds=self._thresholds,
                min_keypoint_confidence=self._min_keypoint_confidence,
            )
            if assessment.evaluated and pose.confidence > best_confidence:
                best = assessment
                best_confidence = pose.confidence
        return best
