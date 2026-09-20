"""Deteccion de permanencia en una zona (dominio puro).

Una ``LoiteringZone`` es un rectangulo normalizado (0..1) del fotograma. El
``ZoneLoiteringMonitor`` acumula frames dentro de la zona por ``track_id`` y
devuelve ``LoiteringSnapshot`` con los tracks que excedieron el umbral de
dwell time (``dwell_threshold_seconds``). La conversion de frames a segundos
se hace en el runner usando el FPS de la camara; el monitor solo acumula
``inside_frames`` y ``outside_frames`` por track.
"""

from dataclasses import dataclass

from recognizer.core.constants import (
    DEFAULT_LOITERING_CONFIRM_FRAMES,
    DEFAULT_LOITERING_RELEASE_FRAMES,
)
from recognizer.core.domain.detection import (
    MAX_NORMALIZED_COORDINATE,
    MIN_NORMALIZED_COORDINATE,
    BoundingBox,
)
from recognizer.core.domain.tracking import TrackedDetection
from recognizer.core.errors import ConfigError


@dataclass(frozen=True, slots=True)
class LoiteringZone:
    """Zona de permanencia normalizada (0..1) del fotograma.

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
class LoiteringSnapshot:
    """Estado de permanencia en un instante: tracks que excedieron el dwell."""

    active: bool
    loiterer_ids: tuple[int, ...]
    dwell_times: dict[int, float]

    @property
    def count(self) -> int:
        """Numero de personas que excedieron el umbral."""
        return len(self.loiterer_ids)


class _ZoneTrackState:
    """Observaciones consecutivas dentro/fuera y tiempo acumulado de un track."""

    __slots__ = ("confirmed", "inside_frames", "outside_frames")

    def __init__(self) -> None:
        self.inside_frames = 0
        self.outside_frames = 0
        self.confirmed = False


class ZoneLoiteringMonitor:
    """Confirma loitering en una zona a partir de detecciones con track persistente.

    Un track se confirma como loiterer cuando su ``inside_frames`` convertido
    a segundos (``inside_frames / fps``) supera ``dwell_threshold_seconds``
    tras ``confirm_frames`` observaciones consecutivas dentro de la zona; se
    libera tras ``release_frames`` observaciones consecutivas fuera (o sin
    aparecer en el fotograma).
    """

    def __init__(
        self,
        *,
        zone: LoiteringZone,
        dwell_threshold_seconds: float,
        confirm_frames: int = DEFAULT_LOITERING_CONFIRM_FRAMES,
        release_frames: int = DEFAULT_LOITERING_RELEASE_FRAMES,
    ) -> None:
        if confirm_frames < 1:
            msg = f"La confirmacion requiere confirm_frames >= 1 (llego {confirm_frames})."
            raise ConfigError(msg)
        if release_frames < 1:
            msg = f"La liberacion requiere release_frames >= 1 (llego {release_frames})."
            raise ConfigError(msg)
        if dwell_threshold_seconds <= 0:
            msg = (
                f"El umbral requiere dwell_threshold_seconds > 0 (llego {dwell_threshold_seconds})."
            )
            raise ConfigError(msg)
        self._zone = zone
        self._dwell_threshold_seconds = dwell_threshold_seconds
        self._confirm_frames = confirm_frames
        self._release_frames = release_frames
        self._states: dict[int, _ZoneTrackState] = {}

    def update(
        self,
        tracked: tuple[TrackedDetection, ...],
        *,
        fps: float,
    ) -> LoiteringSnapshot:
        """Actualiza el estado con las detecciones rastreadas del fotograma.

        Los tracks vistos se evaluan contra la zona; los no vistos cuentan como
        fuera para liberarlos cuando abandonan el encuadre. ``fps`` se usa para
        convertir ``inside_frames`` a segundos y comparar con el umbral.
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
        dwell_times: dict[int, float] = {}
        loiterers: list[int] = []
        for track_id, state in self._states.items():
            dwell_sec = state.inside_frames / fps if fps > 0 else 0.0
            dwell_times[track_id] = dwell_sec
            if state.confirmed and dwell_sec >= self._dwell_threshold_seconds:
                loiterers.append(track_id)
        loiterer_ids = tuple(sorted(loiterers))
        return LoiteringSnapshot(
            active=bool(loiterer_ids),
            loiterer_ids=loiterer_ids,
            dwell_times=dwell_times,
        )

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
