"""Puntero virtual: posicion normalizada y calibracion de la zona activa."""

from dataclasses import dataclass
from enum import StrEnum

from recognizer.core.domain.hand import Point
from recognizer.core.errors import ConfigError

MIN_NORMALIZED_COORDINATE = 0.0
MAX_NORMALIZED_COORDINATE = 1.0
MIRROR_AXIS = 1.0


class SmoothingKind(StrEnum):
    """Estrategias de suavizado disponibles para el puntero."""

    NONE = "none"
    EMA = "ema"


class ScrollDirection(StrEnum):
    """Direcciones de desplazamiento vertical por gestos sostenidos."""

    UP = "up"
    DOWN = "down"


@dataclass(frozen=True, slots=True)
class PointerPosition:
    """Posicion del puntero normalizada respecto a la pantalla."""

    x: float
    y: float


def _clamp01(value: float) -> float:
    """Recorta un valor al rango normalizado 0..1."""
    return max(MIN_NORMALIZED_COORDINATE, min(MAX_NORMALIZED_COORDINATE, value))


@dataclass(frozen=True, slots=True)
class PointerCalibration:
    """Zona activa del fotograma que se proyecta sobre toda la pantalla.

    La zona activa se interpreta en coordenadas especulares (vista selfie);
    la config garantiza min < max.
    """

    x_min: float
    x_max: float
    y_min: float
    y_max: float
    mirror_x: bool = True

    def __post_init__(self) -> None:
        if self.x_min >= self.x_max:
            msg = "La calibracion requiere x_min < x_max."
            raise ConfigError(msg)
        if self.y_min >= self.y_max:
            msg = "La calibracion requiere y_min < y_max."
            raise ConfigError(msg)

    def map(self, point: Point) -> PointerPosition:
        """Proyecta un punto del fotograma a la posicion normalizada del puntero."""
        source_x = MIRROR_AXIS - point.x if self.mirror_x else point.x
        x = (source_x - self.x_min) / (self.x_max - self.x_min)
        y = (point.y - self.y_min) / (self.y_max - self.y_min)
        return PointerPosition(x=_clamp01(x), y=_clamp01(y))
