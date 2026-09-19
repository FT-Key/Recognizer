"""Tracking de objetos y conteo de cruces de una linea (dominio puro).

Una ``CountingLine`` divide el fotograma en dos lados y una banda muerta
(hysteresis) alrededor de la linea. El ``LineCrossingCounter`` asocia a cada
``track_id`` el ultimo lado confirmado y registra un cruce cuando el centro del
objeto supera la banda y se mantiene al lado opuesto durante ``confirm_frames``
observaciones consecutivas (debounce para no contar ruido del tracker). La banda
evita los cruces fantasma de tracks que nacen junto a la linea y el jitter del
centro; los tracks ausentes se purgan tras ``track_timeout_frames`` fotogramas.
"""

from dataclasses import dataclass
from enum import StrEnum

from recognizer.core.constants import (
    DEFAULT_LINE_CONFIRM_FRAMES,
    DEFAULT_LINE_MARGIN,
    DEFAULT_TRACK_TIMEOUT_FRAMES,
)
from recognizer.core.domain.detection import (
    MAX_NORMALIZED_COORDINATE,
    MIN_NORMALIZED_COORDINATE,
    BoundingBox,
    Detection,
)
from recognizer.core.errors import ConfigError

MIN_TRACK_ID = 0
SIDE_POSITIVE = 1
SIDE_NEGATIVE = -1
SIDE_UNKNOWN = 0


@dataclass(frozen=True, slots=True)
class TrackedDetection:
    """Deteccion con identidad de track persistente durante la sesion."""

    track_id: int
    detection: Detection

    def __post_init__(self) -> None:
        if self.track_id < MIN_TRACK_ID:
            msg = f"El track requiere track_id >= {MIN_TRACK_ID} (llego {self.track_id})."
            raise ConfigError(msg)

    @property
    def label(self) -> str:
        """Etiqueta del modelo de la deteccion asociada."""
        return self.detection.label

    @property
    def confidence(self) -> float:
        """Confianza de la deteccion asociada."""
        return self.detection.confidence

    @property
    def bbox(self) -> BoundingBox:
        """Caja normalizada de la deteccion asociada."""
        return self.detection.bbox


class LineAxis(StrEnum):
    """Orientacion de la linea de conteo."""

    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


@dataclass(frozen=True, slots=True)
class CountingLine:
    """Linea de conteo normalizada (0..1) sobre el fotograma.

    Con ``HORIZONTAL`` divide arriba/abajo; con ``VERTICAL`` divide
    izquierda/derecha. ``position`` es la coordenada de la linea en su eje y
    ``margin`` define la banda muerta a ambos lados: dentro de ella la caja no
    pertenece a ningun lado (``SIDE_UNKNOWN``).
    """

    axis: LineAxis
    position: float
    margin: float = DEFAULT_LINE_MARGIN

    def __post_init__(self) -> None:
        if not MIN_NORMALIZED_COORDINATE < self.position < MAX_NORMALIZED_COORDINATE:
            msg = f"La linea requiere 0 < position < 1 (llego {self.position})."
            raise ConfigError(msg)
        max_margin = min(self.position, MAX_NORMALIZED_COORDINATE - self.position)
        if not MIN_NORMALIZED_COORDINATE <= self.margin < max_margin:
            msg = (
                f"El margen requiere 0 <= margin < min(position, 1-position) (llego {self.margin})."
            )
            raise ConfigError(msg)

    def coordinate(self, *, bbox: BoundingBox) -> float:
        """Coordenada del centro de la caja sobre el eje de la linea."""
        if self.axis is LineAxis.HORIZONTAL:
            return bbox.center_y
        return bbox.center_x

    def zone(self, *, bbox: BoundingBox) -> int:
        """Zona de la caja: un lado o la banda muerta (``SIDE_UNKNOWN``).

        Devuelve ``SIDE_POSITIVE`` si el centro supera ``position + margin``,
        ``SIDE_NEGATIVE`` si queda por debajo de ``position - margin`` y
        ``SIDE_UNKNOWN`` dentro de la banda (incluido el centro exacto sobre la
        linea).
        """
        coordinate = self.coordinate(bbox=bbox)
        if coordinate > self.position + self.margin:
            return SIDE_POSITIVE
        if coordinate < self.position - self.margin:
            return SIDE_NEGATIVE
        return SIDE_UNKNOWN


@dataclass(frozen=True, slots=True)
class CrossingSnapshot:
    """Conteo acumulado de entradas y salidas en un instante."""

    entries: int
    exits: int


class _TrackState:
    """Lado confirmado de un track, su pendiente de debounce y su ausencia."""

    __slots__ = ("missing_frames", "pending_count", "pending_side", "side")

    def __init__(self) -> None:
        self.side = SIDE_UNKNOWN
        self.pending_side: int | None = None
        self.pending_count = 0
        self.missing_frames = 0


class LineCrossingCounter:
    """Cuenta cruces de una linea a partir de detecciones con track persistente.

    Sentido positivo del cruce: con ``LineAxis.HORIZONTAL`` va de arriba hacia
    abajo (el centro crece en Y); con ``LineAxis.VERTICAL`` va de izquierda a
    derecha (el centro crece en X). Si ``invert`` es ``False`` el cruce positivo
    cuenta como entrada y el negativo como salida; con ``invert`` se intercambian.

    Un track nuevo arranca en ``SIDE_UNKNOWN``: su lado inicial se fija de
    inmediato en el primer fotograma fuera de la banda muerta (sin contar cruce).
    ``confirm_frames`` solo gobierna los cambios de lado posteriores. Un track
    nacido dentro de la banda sigue en ``SIDE_UNKNOWN`` hasta que sale de ella.
    Los tracks que dejan de verse se purgan tras ``track_timeout_frames``
    fotogramas para no arrastrar IDs muertos.
    """

    def __init__(
        self,
        *,
        line: CountingLine,
        invert: bool = False,
        confirm_frames: int = DEFAULT_LINE_CONFIRM_FRAMES,
        track_timeout_frames: int = DEFAULT_TRACK_TIMEOUT_FRAMES,
    ) -> None:
        if confirm_frames < 1:
            msg = f"La confirmacion requiere confirm_frames >= 1 (llego {confirm_frames})."
            raise ConfigError(msg)
        if track_timeout_frames < 1:
            msg = f"La purga requiere track_timeout_frames >= 1 (llego {track_timeout_frames})."
            raise ConfigError(msg)
        self._line = line
        self._invert = invert
        self._confirm_frames = confirm_frames
        self._track_timeout_frames = track_timeout_frames
        self._states: dict[int, _TrackState] = {}
        self._entries = 0
        self._exits = 0

    @property
    def entries(self) -> int:
        """Total de entradas contadas."""
        return self._entries

    @property
    def exits(self) -> int:
        """Total de salidas contadas."""
        return self._exits

    def update(self, tracked: tuple[TrackedDetection, ...]) -> CrossingSnapshot:
        """Actualiza el conteo con las detecciones rastreadas del fotograma.

        Un track nuevo fija su lado inicial de inmediato en el primer fotograma
        fuera de la banda muerta (sin contar cruce); dentro de la banda el lado
        no cambia. ``confirm_frames`` solo se exige para cambiar de lado. Al
        final purga los tracks ausentes durante ``track_timeout_frames``
        fotogramas.
        """
        seen: set[int] = set()
        for item in tracked:
            seen.add(item.track_id)
            state = self._states.get(item.track_id)
            if state is None:
                state = _TrackState()
                self._states[item.track_id] = state
            state.missing_frames = 0
            zone = self._line.zone(bbox=item.bbox)
            if zone == SIDE_UNKNOWN:
                state.pending_side = None
                state.pending_count = 0
                continue
            if state.side == SIDE_UNKNOWN:
                state.side = zone
                state.pending_side = None
                state.pending_count = 0
                continue
            if zone == state.side:
                state.pending_side = None
                state.pending_count = 0
                continue
            if state.pending_side == zone:
                state.pending_count += 1
            else:
                state.pending_side = zone
                state.pending_count = 1
            if state.pending_count >= self._confirm_frames:
                self._register_crossing(side=zone)
                state.side = zone
                state.pending_side = None
                state.pending_count = 0
        self._purge_states(seen=seen)
        return CrossingSnapshot(entries=self._entries, exits=self._exits)

    def reset(self) -> None:
        """Limpia el estado de tracks y los contadores."""
        self._states.clear()
        self._entries = 0
        self._exits = 0

    def _purge_states(self, *, seen: set[int]) -> None:
        """Incrementa la ausencia de los tracks no vistos y purga los expirados."""
        expired: list[int] = []
        for track_id, state in self._states.items():
            if track_id in seen:
                continue
            state.missing_frames += 1
            if state.missing_frames >= self._track_timeout_frames:
                expired.append(track_id)
        for track_id in expired:
            del self._states[track_id]

    def _register_crossing(self, *, side: int) -> None:
        positive = side == SIDE_POSITIVE
        if self._invert:
            positive = not positive
        if positive:
            self._entries += 1
        else:
            self._exits += 1
