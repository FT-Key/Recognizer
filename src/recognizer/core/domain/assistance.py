"""Deteccion de brazos levantados / pedido de asistencia (dominio puro).

Una persona pide asistencia cuando mantiene las munecas por encima de los
hombros del mismo lado (eje Y hacia abajo: la muneca queda *encima* cuando su
``y`` es menor que la del hombro menos un margen). ``AssistanceMonitor``
confirma el pedido con debounce: hacen falta ``confirm_frames`` fotogramas
consecutivos con alguien levantando los brazos para activar la alerta, y
``release_frames`` sin nadie para liberarla.
"""

from dataclasses import dataclass

from recognizer.core.constants import (
    DEFAULT_ASSISTANCE_CONFIRM_FRAMES,
    DEFAULT_ASSISTANCE_RELEASE_FRAMES,
    DEFAULT_ASSISTANCE_REQUIRED_ARMS,
    MAX_RAISED_ARMS,
    MIN_RAISED_ARMS,
)
from recognizer.core.domain.pose import Pose, PoseKeypoint
from recognizer.core.errors import ConfigError

Point = tuple[float, float]

# Pares hombro-muneca del mismo lado que definen cada brazo.
_ARM_PAIRS: tuple[tuple[PoseKeypoint, PoseKeypoint], ...] = (
    (PoseKeypoint.LEFT_SHOULDER, PoseKeypoint.LEFT_WRIST),
    (PoseKeypoint.RIGHT_SHOULDER, PoseKeypoint.RIGHT_WRIST),
)


@dataclass(frozen=True, slots=True)
class AssistanceSnapshot:
    """Estado del pedido de asistencia tras el debounce."""

    active: bool
    raised: tuple[int, ...] = ()
    people: int = 0


def _point(pose: Pose, name: PoseKeypoint, min_confidence: float) -> Point | None:
    """Punto clave fiable o ``None`` si falta o tiene baja confianza."""
    keypoint = pose.keypoint(name)
    if keypoint is None or keypoint.confidence < min_confidence:
        return None
    return (keypoint.x, keypoint.y)


def raised_arms(pose: Pose, *, min_keypoint_confidence: float, raise_margin: float) -> int:
    """Cuenta los brazos levantados de una postura (0..2).

    Un brazo cuenta cuando su muneca esta por encima del hombro del mismo
    lado al menos ``raise_margin`` (coordenadas normalizadas 0..1). Los
    lados sin hombro o muneca fiable no cuentan.
    """
    count = 0
    for shoulder_name, wrist_name in _ARM_PAIRS:
        shoulder = _point(pose, shoulder_name, min_keypoint_confidence)
        wrist = _point(pose, wrist_name, min_keypoint_confidence)
        if shoulder is None or wrist is None:
            continue
        if wrist[1] + raise_margin < shoulder[1]:
            count += 1
    return count


class AssistanceMonitor:
    """Confirma pedidos de asistencia con debounce por fotogramas.

    Un fotograma "levanta" cuando alguna postura tiene al menos
    ``required_arms`` brazos levantados; la alerta se activa tras
    ``confirm_frames`` fotogramas consecutivos asi y se libera tras
    ``release_frames`` sin nadie levantando los brazos.
    """

    def __init__(
        self,
        *,
        min_keypoint_confidence: float,
        raise_margin: float,
        required_arms: int = DEFAULT_ASSISTANCE_REQUIRED_ARMS,
        confirm_frames: int = DEFAULT_ASSISTANCE_CONFIRM_FRAMES,
        release_frames: int = DEFAULT_ASSISTANCE_RELEASE_FRAMES,
    ) -> None:
        if not MIN_RAISED_ARMS <= required_arms <= MAX_RAISED_ARMS:
            msg = f"La asistencia requiere 1 <= required_arms <= 2 (llego {required_arms})."
            raise ConfigError(msg)
        if raise_margin < 0:
            msg = f"El margen requiere raise_margin >= 0 (llego {raise_margin})."
            raise ConfigError(msg)
        if confirm_frames < 1:
            msg = f"La confirmacion requiere confirm_frames >= 1 (llego {confirm_frames})."
            raise ConfigError(msg)
        if release_frames < 1:
            msg = f"La liberacion requiere release_frames >= 1 (llego {release_frames})."
            raise ConfigError(msg)
        self._min_keypoint_confidence = min_keypoint_confidence
        self._raise_margin = raise_margin
        self._required_arms = required_arms
        self._confirm_frames = confirm_frames
        self._release_frames = release_frames
        self._up_frames = 0
        self._down_frames = 0
        self._active = False

    def update(self, poses: tuple[Pose, ...]) -> AssistanceSnapshot:
        """Actualiza el estado con las posturas del fotograma."""
        raised = tuple(
            index
            for index, pose in enumerate(poses)
            if raised_arms(
                pose,
                min_keypoint_confidence=self._min_keypoint_confidence,
                raise_margin=self._raise_margin,
            )
            >= self._required_arms
        )
        if raised:
            self._up_frames += 1
            self._down_frames = 0
            if self._up_frames >= self._confirm_frames:
                self._active = True
        else:
            self._down_frames += 1
            self._up_frames = 0
            if self._down_frames >= self._release_frames:
                self._active = False
        return AssistanceSnapshot(active=self._active, raised=raised, people=len(poses))

    def reset(self) -> None:
        """Limpia el estado del debounce."""
        self._up_frames = 0
        self._down_frames = 0
        self._active = False
