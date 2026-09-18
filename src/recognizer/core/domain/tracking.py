"""Tracking de objetos y conteo de cruces de una linea (dominio puro).

Una ``CountingLine`` divide el fotograma en dos lados. El ``LineCrossingCounter``
asocia a cada ``track_id`` el ultimo lado confirmado y registra un cruce cuando el
centro del objeto pasa al lado opuesto durante ``confirm_frames`` observaciones
consecutivas (debounce para no contar ruido del tracker).
"""

from dataclasses import dataclass
from enum import StrEnum

from recognizer.core.constants import DEFAULT_LINE_CONFIRM_FRAMES
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
    izquierda/derecha. ``position`` es la coordenada de la linea en su eje.
    """

    axis: LineAxis
    position: float

    def __post_init__(self) -> None:
        if not MIN_NORMALIZED_COORDINATE < self.position < MAX_NORMALIZED_COORDINATE:
            msg = f"La linea requiere 0 < position < 1 (llego {self.position})."
            raise ConfigError(msg)

    def coordinate(self, *, bbox: BoundingBox) -> float:
        """Coordenada del centro de la caja sobre el eje de la linea."""
        if self.axis is LineAxis.HORIZONTAL:
            return bbox.center_y
        return bbox.center_x

    def side(self, *, bbox: BoundingBox) -> int:
        """Lado de la caja: ``SIDE_POSITIVE`` si supera la linea, si no ``SIDE_NEGATIVE``."""
        return SIDE_POSITIVE if self.coordinate(bbox=bbox) > self.position else SIDE_NEGATIVE


@dataclass(frozen=True, slots=True)
class CrossingSnapshot:
    """Conteo acumulado de entradas y salidas en un instante."""

    entries: int
    exits: int


class _TrackState:
    """Lado confirmado de un track y su pendiente de debounce."""

    __slots__ = ("pending_count", "pending_side", "side")

    def __init__(self, *, side: int) -> None:
        self.side = side
        self.pending_side: int | None = None
        self.pending_count = 0


class LineCrossingCounter:
    """Cuenta cruces de una linea a partir de detecciones con track persistente.

    Sentido positivo del cruce: con ``LineAxis.HORIZONTAL`` va de arriba hacia
    abajo (el centro crece en Y); con ``LineAxis.VERTICAL`` va de izquierda a
    derecha (el centro crece en X). Si ``invert`` es ``False`` el cruce positivo
    cuenta como entrada y el negativo como salida; con ``invert`` se intercambian.

    No se purgan los IDs vistos: los IDs de una sesion de tracking son acotados
    y el estado por track es minimo, por lo que no hay fuga relevante.
    """

    def __init__(
        self,
        *,
        line: CountingLine,
        invert: bool = False,
        confirm_frames: int = DEFAULT_LINE_CONFIRM_FRAMES,
    ) -> None:
        if confirm_frames < 1:
            msg = f"La confirmacion requiere confirm_frames >= 1 (llego {confirm_frames})."
            raise ConfigError(msg)
        self._line = line
        self._invert = invert
        self._confirm_frames = confirm_frames
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

        Un track nuevo se inicializa en su lado actual sin contar cruce.
        """
        for item in tracked:
            side = self._line.side(bbox=item.bbox)
            state = self._states.get(item.track_id)
            if state is None:
                self._states[item.track_id] = _TrackState(side=side)
                continue
            if side == state.side:
                state.pending_side = None
                state.pending_count = 0
                continue
            if state.pending_side == side:
                state.pending_count += 1
            else:
                state.pending_side = side
                state.pending_count = 1
            if state.pending_count >= self._confirm_frames:
                self._register_crossing(side=side)
                state.side = side
                state.pending_side = None
                state.pending_count = 0
        return CrossingSnapshot(entries=self._entries, exits=self._exits)

    def reset(self) -> None:
        """Limpia el estado de tracks y los contadores."""
        self._states.clear()
        self._entries = 0
        self._exits = 0

    def _register_crossing(self, *, side: int) -> None:
        positive = side == SIDE_POSITIVE
        if self._invert:
            positive = not positive
        if positive:
            self._entries += 1
        else:
            self._exits += 1
