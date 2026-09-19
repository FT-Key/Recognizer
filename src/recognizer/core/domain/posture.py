"""Evaluacion de postura ergonomica (dominio puro).

La medicion es **parcial**: cada metrica se calcula con los puntos clave que
estan disponibles y con confianza suficiente, de modo que la postura se sigue
evaluando aunque las caderas queden ocultas por el escritorio (habitual al
sentarse) o aunque falte un hombro (vista de perfil).

`PostureMonitor` aprende la postura correcta durante una calibracion inicial
(`calibration_frames` fotogramas) y luego avisa cuando la postura se desvia de
esa linea base mas de las tolerancias configuradas. Si la calibracion esta
desactivada (`calibration_frames == 0`) usa umbrales absolutos.
"""

import math
import statistics
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from recognizer.core.constants import (
    DEFAULT_POSTURE_CONFIRM_FRAMES,
    DEFAULT_POSTURE_MAX_HEAD_OFFSET_RATIO,
    DEFAULT_POSTURE_MAX_SHOULDER_TILT_RATIO,
    DEFAULT_POSTURE_MAX_TORSO_ANGLE_DEG,
    DEFAULT_POSTURE_MIN_HEAD_HEIGHT_RATIO,
    DEFAULT_POSTURE_RELEASE_FRAMES,
    DEFAULT_POSTURE_TOLERANCE_HEAD_HEIGHT,
    DEFAULT_POSTURE_TOLERANCE_HEAD_OFFSET,
    DEFAULT_POSTURE_TOLERANCE_SHOULDER_TILT,
    DEFAULT_POSTURE_TOLERANCE_TORSO_ANGLE_DEG,
    MIN_VECTOR_NORM,
    POSTURE_PROFILE_SHOULDER_RATIO,
)
from recognizer.core.domain.pose import Pose, PoseKeypoint
from recognizer.core.errors import ConfigError

Point = tuple[float, float]


class PostureIssue(StrEnum):
    """Habito postural incorrecto detectado."""

    HEAD_FORWARD = "cabeza adelante"
    HEAD_DROP = "cabeza baja"
    TORSO_LEAN = "espalda inclinada"
    SHOULDER_TILT = "hombros desnivelados"


# Metrica de `PostureMetrics` que sustenta cada aviso (para el debounce).
_ISSUE_METRIC: dict[PostureIssue, str] = {
    PostureIssue.HEAD_FORWARD: "head_offset_ratio",
    PostureIssue.HEAD_DROP: "head_height_ratio",
    PostureIssue.TORSO_LEAN: "torso_angle_deg",
    PostureIssue.SHOULDER_TILT: "shoulder_tilt_ratio",
}


@dataclass(frozen=True, slots=True)
class PostureThresholds:
    """Umbrales absolutos (fallback sin calibracion)."""

    max_head_offset_ratio: float = DEFAULT_POSTURE_MAX_HEAD_OFFSET_RATIO
    min_head_height_ratio: float = DEFAULT_POSTURE_MIN_HEAD_HEIGHT_RATIO
    max_torso_angle_deg: float = DEFAULT_POSTURE_MAX_TORSO_ANGLE_DEG
    max_shoulder_tilt_ratio: float = DEFAULT_POSTURE_MAX_SHOULDER_TILT_RATIO


@dataclass(frozen=True, slots=True)
class PostureTolerances:
    """Desvio admitido respecto a la linea base calibrada."""

    head_offset: float = DEFAULT_POSTURE_TOLERANCE_HEAD_OFFSET
    head_height: float = DEFAULT_POSTURE_TOLERANCE_HEAD_HEIGHT
    torso_angle_deg: float = DEFAULT_POSTURE_TOLERANCE_TORSO_ANGLE_DEG
    shoulder_tilt: float = DEFAULT_POSTURE_TOLERANCE_SHOULDER_TILT


@dataclass(frozen=True, slots=True)
class PostureMetrics:
    """Metricas normalizadas de una postura; cada una puede faltar (``None``)."""

    head_offset_ratio: float | None = None
    head_height_ratio: float | None = None
    torso_angle_deg: float | None = None
    shoulder_tilt_ratio: float | None = None

    def any_available(self) -> bool:
        """Indica si al menos una metrica pudo calcularse."""
        return any(
            value is not None
            for value in (
                self.head_offset_ratio,
                self.head_height_ratio,
                self.torso_angle_deg,
                self.shoulder_tilt_ratio,
            )
        )


@dataclass(frozen=True, slots=True)
class PostureBaseline:
    """Linea base aprendida durante la calibracion (mediana por metrica)."""

    head_offset_ratio: float | None = None
    head_height_ratio: float | None = None
    torso_angle_deg: float | None = None
    shoulder_tilt_ratio: float | None = None


@dataclass(frozen=True, slots=True)
class PostureAssessment:
    """Resultado de evaluar una postura contra los umbrales absolutos."""

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
    calibrating: bool = False


def _point(pose: Pose, name: PoseKeypoint, min_confidence: float) -> Point | None:
    """Punto clave fiable o ``None`` si falta o tiene baja confianza."""
    keypoint = pose.keypoint(name)
    if keypoint is None or keypoint.confidence < min_confidence:
        return None
    return (keypoint.x, keypoint.y)


def _center(first: Point | None, second: Point | None) -> Point | None:
    """Centro de dos puntos; si solo uno esta visible, ese mismo.

    En vista de perfil el hombro/cadera lejano suele quedar oculto: usar el
    punto visible permite seguir midiendo (la calibracion absorbe el sesgo).
    """
    if first is not None and second is not None:
        return ((first[0] + second[0]) / 2, (first[1] + second[1]) / 2)
    return first if first is not None else second


def _body_scale(
    shoulder_width: float | None,
    torso_length: float | None,
    head_width: float | None,
) -> float | None:
    """Escala corporal de referencia, robusta a la vista de perfil.

    Prioriza el ancho de hombros; en perfil (hombros solapados o un solo hombro
    visible) usa el largo del torso y, si no hay caderas, el tamano de la cabeza.
    """
    if shoulder_width is not None and torso_length is not None:
        if shoulder_width >= POSTURE_PROFILE_SHOULDER_RATIO * torso_length:
            return shoulder_width
        return torso_length
    if torso_length is not None:
        return torso_length
    if shoulder_width is not None:
        if head_width is not None and shoulder_width < head_width:
            return head_width
        return shoulder_width
    return head_width


def _head_width(
    nose: Point | None, left_ear: Point | None, right_ear: Point | None
) -> float | None:
    """Referencia de tamano de la cabeza (orejas, o nariz-oreja si falta una)."""
    if left_ear is not None and right_ear is not None:
        return math.dist(left_ear, right_ear)
    if nose is not None and left_ear is not None:
        return math.dist(nose, left_ear)
    if nose is not None and right_ear is not None:
        return math.dist(nose, right_ear)
    return None


def _torso_angle(shoulder_center: Point | None, hip_center: Point | None) -> float | None:
    """Angulo (grados) de la linea hombros-caderas respecto a la vertical."""
    if shoulder_center is None or hip_center is None:
        return None
    dy = hip_center[1] - shoulder_center[1]
    if dy <= MIN_VECTOR_NORM:
        return None
    return math.degrees(math.atan2(abs(hip_center[0] - shoulder_center[0]), dy))


def measure_posture(pose: Pose, *, min_keypoint_confidence: float) -> PostureMetrics | None:
    """Calcula las metricas disponibles de una postura; ``None`` si no hay escala."""
    left_shoulder = _point(pose, PoseKeypoint.LEFT_SHOULDER, min_keypoint_confidence)
    right_shoulder = _point(pose, PoseKeypoint.RIGHT_SHOULDER, min_keypoint_confidence)
    left_hip = _point(pose, PoseKeypoint.LEFT_HIP, min_keypoint_confidence)
    right_hip = _point(pose, PoseKeypoint.RIGHT_HIP, min_keypoint_confidence)
    nose = _point(pose, PoseKeypoint.NOSE, min_keypoint_confidence)
    left_ear = _point(pose, PoseKeypoint.LEFT_EAR, min_keypoint_confidence)
    right_ear = _point(pose, PoseKeypoint.RIGHT_EAR, min_keypoint_confidence)

    shoulder_center = _center(left_shoulder, right_shoulder)
    hip_center = _center(left_hip, right_hip)
    shoulder_width = (
        math.dist(left_shoulder, right_shoulder)
        if left_shoulder is not None and right_shoulder is not None
        else None
    )
    torso_length = (
        math.dist(shoulder_center, hip_center)
        if shoulder_center is not None and hip_center is not None
        else None
    )
    scale = _body_scale(shoulder_width, torso_length, _head_width(nose, left_ear, right_ear))
    if scale is None or scale <= MIN_VECTOR_NORM:
        return None

    head_offset = (
        abs(nose[0] - shoulder_center[0]) / scale
        if nose is not None and shoulder_center is not None
        else None
    )
    head_height = (
        (shoulder_center[1] - nose[1]) / scale
        if nose is not None and shoulder_center is not None
        else None
    )
    shoulder_tilt = (
        abs(left_shoulder[1] - right_shoulder[1]) / scale
        if left_shoulder is not None and right_shoulder is not None
        else None
    )
    metrics = PostureMetrics(
        head_offset_ratio=head_offset,
        head_height_ratio=head_height,
        torso_angle_deg=_torso_angle(shoulder_center, hip_center),
        shoulder_tilt_ratio=shoulder_tilt,
    )
    return metrics if metrics.any_available() else None


def _issues_from_thresholds(
    metrics: PostureMetrics, thresholds: PostureThresholds
) -> tuple[PostureIssue, ...]:
    issues: list[PostureIssue] = []
    if (
        metrics.head_offset_ratio is not None
        and metrics.head_offset_ratio > thresholds.max_head_offset_ratio
    ):
        issues.append(PostureIssue.HEAD_FORWARD)
    if (
        metrics.head_height_ratio is not None
        and metrics.head_height_ratio < thresholds.min_head_height_ratio
    ):
        issues.append(PostureIssue.HEAD_DROP)
    if (
        metrics.torso_angle_deg is not None
        and metrics.torso_angle_deg > thresholds.max_torso_angle_deg
    ):
        issues.append(PostureIssue.TORSO_LEAN)
    if (
        metrics.shoulder_tilt_ratio is not None
        and metrics.shoulder_tilt_ratio > thresholds.max_shoulder_tilt_ratio
    ):
        issues.append(PostureIssue.SHOULDER_TILT)
    return tuple(issues)


def _issues_from_baseline(
    metrics: PostureMetrics,
    baseline: PostureBaseline,
    tolerances: PostureTolerances,
) -> tuple[PostureIssue, ...]:
    issues: list[PostureIssue] = []
    if (
        metrics.head_offset_ratio is not None
        and baseline.head_offset_ratio is not None
        and metrics.head_offset_ratio > baseline.head_offset_ratio + tolerances.head_offset
    ):
        issues.append(PostureIssue.HEAD_FORWARD)
    if (
        metrics.head_height_ratio is not None
        and baseline.head_height_ratio is not None
        and metrics.head_height_ratio < baseline.head_height_ratio - tolerances.head_height
    ):
        issues.append(PostureIssue.HEAD_DROP)
    if (
        metrics.torso_angle_deg is not None
        and baseline.torso_angle_deg is not None
        and metrics.torso_angle_deg > baseline.torso_angle_deg + tolerances.torso_angle_deg
    ):
        issues.append(PostureIssue.TORSO_LEAN)
    if (
        metrics.shoulder_tilt_ratio is not None
        and baseline.shoulder_tilt_ratio is not None
        and metrics.shoulder_tilt_ratio > baseline.shoulder_tilt_ratio + tolerances.shoulder_tilt
    ):
        issues.append(PostureIssue.SHOULDER_TILT)
    return tuple(issues)


def assess_posture(
    pose: Pose,
    *,
    thresholds: PostureThresholds,
    min_keypoint_confidence: float,
) -> PostureAssessment:
    """Evalua una postura contra umbrales absolutos (sin calibracion)."""
    metrics = measure_posture(pose, min_keypoint_confidence=min_keypoint_confidence)
    if metrics is None:
        return PostureAssessment(evaluated=False)
    return PostureAssessment(evaluated=True, issues=_issues_from_thresholds(metrics, thresholds))


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _column(
    samples: list[PostureMetrics], selector: Callable[[PostureMetrics], float | None]
) -> list[float]:
    return [value for sample in samples if (value := selector(sample)) is not None]


def _compute_baseline(samples: list[PostureMetrics]) -> PostureBaseline:
    return PostureBaseline(
        head_offset_ratio=_median(_column(samples, lambda sample: sample.head_offset_ratio)),
        head_height_ratio=_median(_column(samples, lambda sample: sample.head_height_ratio)),
        torso_angle_deg=_median(_column(samples, lambda sample: sample.torso_angle_deg)),
        shoulder_tilt_ratio=_median(_column(samples, lambda sample: sample.shoulder_tilt_ratio)),
    )


class PostureMonitor:
    """Aprende la postura correcta y avisa de desvios con debounce.

    Durante ``calibration_frames`` fotogramas evaluables acumula metricas y fija
    la mediana como linea base; despues, cada fotograma se compara con esa linea
    base (o con los umbrales absolutos si la calibracion esta desactivada).
    """

    def __init__(
        self,
        *,
        thresholds: PostureThresholds,
        min_keypoint_confidence: float,
        confirm_frames: int = DEFAULT_POSTURE_CONFIRM_FRAMES,
        release_frames: int = DEFAULT_POSTURE_RELEASE_FRAMES,
        calibration_frames: int = 0,
        tolerances: PostureTolerances | None = None,
    ) -> None:
        if confirm_frames < 1:
            msg = f"La confirmacion requiere confirm_frames >= 1 (llego {confirm_frames})."
            raise ConfigError(msg)
        if release_frames < 1:
            msg = f"La liberacion requiere release_frames >= 1 (llego {release_frames})."
            raise ConfigError(msg)
        if calibration_frames < 0:
            msg = f"La calibracion requiere calibration_frames >= 0 (llego {calibration_frames})."
            raise ConfigError(msg)
        self._thresholds = thresholds
        self._tolerances = tolerances if tolerances is not None else PostureTolerances()
        self._min_keypoint_confidence = min_keypoint_confidence
        self._confirm_frames = confirm_frames
        self._release_frames = release_frames
        self._calibration_frames = calibration_frames
        self._calibration: list[PostureMetrics] = []
        self._baseline: PostureBaseline | None = None
        self._calibrating = calibration_frames > 0
        self._bad_frames = 0
        self._good_frames = 0
        self._missing_frames = 0
        self._active = False
        self._issues: tuple[PostureIssue, ...] = ()

    @property
    def calibrating(self) -> bool:
        """Indica si aun se esta aprendiendo la linea base."""
        return self._calibrating

    def update(self, poses: tuple[Pose, ...]) -> PostureSnapshot:
        """Actualiza el estado con las posturas del fotograma."""
        metrics = self._primary_metrics(poses)
        if self._calibrating:
            self._collect_calibration(metrics)
            return PostureSnapshot(active=False, calibrating=True)
        if metrics is None:
            self._on_missing()
        else:
            issues = self._evaluate(metrics)
            if issues:
                self._on_bad(issues)
            elif self._active and not self._covers_active_issues(metrics):
                # El fotograma no trae la metrica que disparo el aviso (p. ej.
                # se perdio la nariz): no cuenta como postura correcta.
                self._on_missing()
            else:
                self._on_good()
        return PostureSnapshot(active=self._active, issues=self._issues)

    def reset(self) -> None:
        """Limpia el estado del debounce y de la calibracion."""
        self._calibration = []
        self._baseline = None
        self._calibrating = self._calibration_frames > 0
        self._bad_frames = 0
        self._good_frames = 0
        self._missing_frames = 0
        self._active = False
        self._issues = ()

    def _collect_calibration(self, metrics: PostureMetrics | None) -> None:
        if metrics is None:
            return
        self._calibration.append(metrics)
        if len(self._calibration) >= self._calibration_frames:
            self._baseline = _compute_baseline(self._calibration)
            self._calibrating = False

    def _evaluate(self, metrics: PostureMetrics) -> tuple[PostureIssue, ...]:
        """Evalua las metricas contra la linea base o los umbrales absolutos."""
        if self._baseline is not None:
            return _issues_from_baseline(metrics, self._baseline, self._tolerances)
        return _issues_from_thresholds(metrics, self._thresholds)

    def _covers_active_issues(self, metrics: PostureMetrics) -> bool:
        """Indica si el fotograma trae las metricas de los avisos activos."""
        values: dict[str, float | None] = {
            "head_offset_ratio": metrics.head_offset_ratio,
            "head_height_ratio": metrics.head_height_ratio,
            "torso_angle_deg": metrics.torso_angle_deg,
            "shoulder_tilt_ratio": metrics.shoulder_tilt_ratio,
        }
        return all(values[_ISSUE_METRIC[issue]] is not None for issue in self._issues)

    def _primary_metrics(self, poses: tuple[Pose, ...]) -> PostureMetrics | None:
        """Metricas de la persona con mayor confianza que sea evaluable."""
        best: PostureMetrics | None = None
        best_confidence = -1.0
        for pose in poses:
            metrics = measure_posture(pose, min_keypoint_confidence=self._min_keypoint_confidence)
            if metrics is not None and pose.confidence > best_confidence:
                best = metrics
                best_confidence = pose.confidence
        return best

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
        """Un cuadro no evaluable no rompe la racha de mala postura.

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
