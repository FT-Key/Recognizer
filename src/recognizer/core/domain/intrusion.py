"""Deteccion de intrusion en una zona (dominio puro).

Una ``IntrusionZone`` es un rectangulo normalizado (0..1) del fotograma. El
``ZoneIntrusionMonitor`` decide que tracks estan dentro de la zona con un
debounce: un track debe permanecer ``confirm_frames`` observaciones dentro para
confirmarse como intruso, y ``release_frames`` fuera (o ausente) para liberarse.
Asi se evita alertar por ruido del tracker o por un objeto que solo cruza.
"""

from dataclasses import dataclass

from recognizer.core.constants import (
    DEFAULT_INTRUSION_CONFIRM_FRAMES,
    DEFAULT_INTRUSION_RELEASE_FRAMES,
)
from recognizer.core.domain.detection import (
    MAX_NORMALIZED_COORDINATE,
    MIN_NORMALIZED_COORDINATE,
    BoundingBox,
)
from recognizer.core.domain.tracking import TrackedDetection
from recognizer.core.errors import ConfigError


@dataclass(frozen=True, slots=True)
class IntrusionZone:
    """Zona de intrusion normalizada (0..1) del fotograma.

    La pertenencia se evalua con el centro de la caja: un objeto esta en la zona
    si su centro cae dentro del rectangulo.
    """

    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def __post_init__(self) -> None:
        for name, value in (
            ("x_min", self.x_min),
            ("y_min", self.y_min),
            ("x_max", self.x_max),
            ("y_max", self.y_max),
        ):
            if not MIN_NORMALIZED_COORDINATE <= value <= MAX_NORMALIZED_COORDINATE:
                msg = f"La zona requiere 0 <= {name} <= 1 (llego {value})."
                raise ConfigError(msg)
        if self.x_min >= self.x_max:
            msg = "La zona requiere x_min < x_max."
            raise ConfigError(msg)
        if self.y_min >= self.y_max:
            msg = "La zona requiere y_min < y_max."
            raise ConfigError(msg)

    def contains(self, *, bbox: BoundingBox) -> bool:
        """Indica si el centro de la caja cae dentro de la zona."""
        return (
            self.x_min <= bbox.center_x <= self.x_max and self.y_min <= bbox.center_y <= self.y_max
        )


@dataclass(frozen=True, slots=True)
class IntrusionSnapshot:
    """Estado de intrusion en un instante: tracks confirmados dentro de la zona."""

    active: bool
    intruder_ids: tuple[int, ...]

    @property
    def count(self) -> int:
        """Numero de intrusos confirmados."""
        return len(self.intruder_ids)


class _ZoneTrackState:
    """Observaciones consecutivas dentro/fuera y confirmacion de un track."""

    __slots__ = ("confirmed", "inside_frames", "outside_frames")

    def __init__(self) -> None:
        self.inside_frames = 0
        self.outside_frames = 0
        self.confirmed = False


class ZoneIntrusionMonitor:
    """Confirma intrusos en una zona a partir de detecciones con track persistente.

    Un track se confirma como intruso tras ``confirm_frames`` observaciones
    consecutivas dentro de la zona; se libera tras ``release_frames``
    observaciones consecutivas fuera (o sin aparecer en el fotograma).
    """

    def __init__(
        self,
        *,
        zone: IntrusionZone,
        confirm_frames: int = DEFAULT_INTRUSION_CONFIRM_FRAMES,
        release_frames: int = DEFAULT_INTRUSION_RELEASE_FRAMES,
    ) -> None:
        if confirm_frames < 1:
            msg = f"La confirmacion requiere confirm_frames >= 1 (llego {confirm_frames})."
            raise ConfigError(msg)
        if release_frames < 1:
            msg = f"La liberacion requiere release_frames >= 1 (llego {release_frames})."
            raise ConfigError(msg)
        self._zone = zone
        self._confirm_frames = confirm_frames
        self._release_frames = release_frames
        self._states: dict[int, _ZoneTrackState] = {}

    def update(self, tracked: tuple[TrackedDetection, ...]) -> IntrusionSnapshot:
        """Actualiza el estado con las detecciones rastreadas del fotograma.

        Los tracks vistos se evaluan contra la zona; los no vistos cuentan como
        fuera para liberarlos cuando abandonan el encuadre.
        """
        seen: set[int] = set()
        for item in tracked:
            seen.add(item.track_id)
            state = self._states.get(item.track_id)
            if state is None:
                state = _ZoneTrackState()
                self._states[item.track_id] = state
            if self._zone.contains(bbox=item.bbox):
                state.inside_frames += 1
                state.outside_frames = 0
                if state.inside_frames >= self._confirm_frames:
                    state.confirmed = True
            else:
                self._mark_outside(state)
        for track_id, state in self._states.items():
            if track_id not in seen:
                self._mark_outside(state)
        self._purge_released()
        intruders = tuple(
            sorted(track_id for track_id, state in self._states.items() if state.confirmed)
        )
        return IntrusionSnapshot(active=bool(intruders), intruder_ids=intruders)

    def reset(self) -> None:
        """Limpia el estado de tracks."""
        self._states.clear()

    def _mark_outside(self, state: _ZoneTrackState) -> None:
        state.outside_frames += 1
        state.inside_frames = 0
        if state.outside_frames >= self._release_frames:
            state.confirmed = False

    def _purge_released(self) -> None:
        """Descarta tracks ya liberados para acotar el estado de la sesion.

        Un track purgado que reaparezca se trata como nuevo y debe volver a
        confirmarse dentro de la zona.
        """
        released = [
            track_id
            for track_id, state in self._states.items()
            if not state.confirmed and state.outside_frames >= self._release_frames
        ]
        for track_id in released:
            del self._states[track_id]
