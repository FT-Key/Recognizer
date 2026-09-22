"""Deteccion de caidas (dominio puro).

Un ``FallDetector`` evalua si alguna persona ha caido analizando la pose
estimada por YOLO pose. La deteccion combina tres senales:

1. **Aspecto** (``aspect_ratio``): relacion alto/ancho del cuerpo. Una persona
   de pie tiene un aspecto vertical (>1); al caer el cuerpo se vuelve mas
   horizontal (<1). Se calcula como ``altura / ancho`` usando los hombros y
   las caderas (o rodillas si las caderas no estan visibles).

2. **Centro bajo** (``center_y``): la posicion Y del centro de masa del cuerpo
   es mayor (mas abajo en la imagen) cuando la persona esta en el suelo.
   Se normaliza respecto a la altura del fotograma (0 = arriba, 1 = abajo).

3. **Quietud** (``stillness``): una persona caida se mueve menos que una de
   pie. Se mide con la varianza del centro de masa entre ``stillness_window``
   fotogramas consecutivos; poca varianza = quietud = candidata a caida.

Una caida se confirma cuando las tres senales superan sus umbrales durante
``confirm_frames`` fotogramas consecutivos. La alerta se libera tras
``release_frames`` fotogramas sin senales de caida.
"""

import math
from collections import deque
from dataclasses import dataclass

from recognizer.core.constants import MIN_VECTOR_NORM
from recognizer.core.domain.pose import Pose, PoseKeypoint
from recognizer.core.errors import ConfigError

Point = tuple[float, float]


@dataclass(frozen=True, slots=True)
class FallMetrics:
    """Metricas extraidas de una postura para evaluar una posible caida."""

    aspect_ratio: float | None = None
    center_y: float | None = None
    stillness: float | None = None

    def any_available(self) -> bool:
        """Indica si al menos una metrica pudo calcularse."""
        return any(
            value is not None for value in (self.aspect_ratio, self.center_y, self.stillness)
        )


@dataclass(frozen=True, slots=True)
class FallSnapshot:
    """Estado confirmado de la deteccion de caida tras el debounce."""

    active: bool
    fallen: tuple[int, ...] = ()
    people: int = 0


def _point(pose: Pose, name: PoseKeypoint, min_confidence: float) -> Point | None:
    """Punto clave fiable o ``None`` si falta o tiene baja confianza."""
    keypoint = pose.keypoint(name)
    if keypoint is None or keypoint.confidence < min_confidence:
        return None
    return (keypoint.x, keypoint.y)


def _center(first: Point | None, second: Point | None) -> Point | None:
    """Centro de dos puntos; si solo uno esta visible, ese mismo."""
    if first is not None and second is not None:
        return ((first[0] + second[0]) / 2, (first[1] + second[1]) / 2)
    return first if first is not None else second


def _body_bbox(pose: Pose, *, min_keypoint_confidence: float) -> tuple[Point, Point] | None:
    """Bounding box del torso (hombros + caderas/rodillas).

    Devuelve (top_left, bottom_right) en coordenadas normalizadas o ``None``
    si no hay suficientes puntos.
    """
    left_shoulder = _point(pose, PoseKeypoint.LEFT_SHOULDER, min_keypoint_confidence)
    right_shoulder = _point(pose, PoseKeypoint.RIGHT_SHOULDER, min_keypoint_confidence)
    left_hip = _point(pose, PoseKeypoint.LEFT_HIP, min_keypoint_confidence)
    right_hip = _point(pose, PoseKeypoint.RIGHT_HIP, min_keypoint_confidence)

    # Fallback: rodillas si las caderas no estan visibles.
    if left_hip is None or right_hip is None:
        left_hip = left_hip or _point(pose, PoseKeypoint.LEFT_KNEE, min_keypoint_confidence)
        right_hip = right_hip or _point(pose, PoseKeypoint.RIGHT_KNEE, min_keypoint_confidence)

    shoulder_center = _center(left_shoulder, right_shoulder)
    hip_center = _center(left_hip, right_hip)

    if shoulder_center is None or hip_center is None:
        return None

    x_min = min(
        left_shoulder[0] if left_shoulder is not None else shoulder_center[0],
        right_shoulder[0] if right_shoulder is not None else shoulder_center[0],
        left_hip[0] if left_hip is not None else hip_center[0],
        right_hip[0] if right_hip is not None else hip_center[0],
    )
    x_max = max(
        left_shoulder[0] if left_shoulder is not None else shoulder_center[0],
        right_shoulder[0] if right_shoulder is not None else shoulder_center[0],
        left_hip[0] if left_hip is not None else hip_center[0],
        right_hip[0] if right_hip is not None else hip_center[0],
    )
    y_min = min(shoulder_center[1], hip_center[1])
    y_max = max(shoulder_center[1], hip_center[1])

    return (x_min, y_min), (x_max, y_max)


def measure_fall(
    pose: Pose,
    *,
    min_keypoint_confidence: float,
    stillness: float | None = None,
) -> FallMetrics | None:
    """Calcula las metricas de caida disponibles; ``None`` si no hay escala."""
    bbox = _body_bbox(pose, min_keypoint_confidence=min_keypoint_confidence)
    if bbox is None:
        return None

    (x_min, y_min), (x_max, y_max) = bbox
    width = x_max - x_min
    height = y_max - y_min

    if width < MIN_VECTOR_NORM or height < MIN_VECTOR_NORM:
        return None

    aspect_ratio = height / width
    center_y = (y_min + y_max) / 2

    return FallMetrics(
        aspect_ratio=aspect_ratio,
        center_y=center_y,
        stillness=stillness,
    )


class FallDetector:
    """Detecta caidas con debounce por fotogramas.

    Evalua cada postura con ``measure_fall`` y marca una caida cuando el
    aspecto, el centro Y y la quietud superan sus umbrales durante
    ``confirm_frames`` fotogramas consecutivos.
    """

    def __init__(
        self,
        *,
        min_keypoint_confidence: float,
        max_aspect_ratio: float,
        min_center_y: float,
        max_stillness: float,
        stillness_window: int,
        confirm_frames: int,
        release_frames: int,
    ) -> None:
        if confirm_frames < 1:
            msg = f"La confirmacion requiere confirm_frames >= 1 (llego {confirm_frames})."
            raise ConfigError(msg)
        if release_frames < 1:
            msg = f"La liberacion requiere release_frames >= 1 (llego {release_frames})."
            raise ConfigError(msg)
        if stillness_window < 1:
            msg = (
                f"La ventana de quietud requiere stillness_window >= 1 (llego {stillness_window})."
            )
            raise ConfigError(msg)
        self._min_keypoint_confidence = min_keypoint_confidence
        self._max_aspect_ratio = max_aspect_ratio
        self._min_center_y = min_center_y
        self._max_stillness = max_stillness
        self._stillness_window = stillness_window
        self._confirm_frames = confirm_frames
        self._release_frames = release_frames
        self._up_frames = 0
        self._down_frames = 0
        self._active = False
        # Historial de centros Y por persona (track_id) para calcular quietud.
        self._center_history: dict[int, deque[float]] = {}

    def _compute_stillness(self, track_id: int, center_y: float) -> float:
        """Calcula la quietud (varianza del centro Y en la ventana)."""
        history = self._center_history.get(track_id)
        if history is None:
            history = deque(maxlen=self._stillness_window)
            self._center_history[track_id] = history
        history.append(center_y)
        if len(history) < 2:
            return float("inf")
        mean = sum(history) / len(history)
        variance = sum((y - mean) ** 2 for y in history) / len(history)
        return math.sqrt(variance)

    def _is_fallen(self, metrics: FallMetrics, track_id: int) -> bool:
        """Evalua si las metricas indican una caida."""
        if metrics.aspect_ratio is None or metrics.center_y is None:
            return False
        if metrics.aspect_ratio > self._max_aspect_ratio:
            return False
        if metrics.center_y < self._min_center_y:
            return False
        stillness = self._compute_stillness(track_id, metrics.center_y)
        return not stillness > self._max_stillness

    def update(self, poses: tuple[Pose, ...]) -> FallSnapshot:
        """Actualiza el estado con las posturas del fotograma."""
        fallen = tuple(
            index
            for index, pose in enumerate(poses)
            if self._is_fallen(
                measure_fall(
                    pose,
                    min_keypoint_confidence=self._min_keypoint_confidence,
                )
                or FallMetrics(),
                track_id=index,
            )
        )
        if fallen:
            self._up_frames += 1
            self._down_frames = 0
            if self._up_frames >= self._confirm_frames:
                self._active = True
        else:
            self._down_frames += 1
            self._up_frames = 0
            if self._down_frames >= self._release_frames:
                self._active = False
        return FallSnapshot(active=self._active, fallen=fallen, people=len(poses))

    def reset(self) -> None:
        """Limpia el estado del debounce y del historial."""
        self._up_frames = 0
        self._down_frames = 0
        self._active = False
        self._center_history.clear()
