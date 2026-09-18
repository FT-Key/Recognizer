"""Detecciones genericas de objetos (YOLO hoy, otro motor en el futuro)."""

from dataclasses import dataclass

from recognizer.core.constants import PERSON_LABEL
from recognizer.core.errors import ConfigError

MIN_NORMALIZED_COORDINATE = 0.0
MAX_NORMALIZED_COORDINATE = 1.0
MIN_CONFIDENCE = 0.0
MAX_CONFIDENCE = 1.0


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Caja envolvente normalizada respecto al fotograma (rango 0..1)."""

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
                msg = f"La caja requiere 0 <= {name} <= 1 (llego {value})."
                raise ConfigError(msg)
        if self.x_min >= self.x_max:
            msg = "La caja requiere x_min < x_max."
            raise ConfigError(msg)
        if self.y_min >= self.y_max:
            msg = "La caja requiere y_min < y_max."
            raise ConfigError(msg)

    @property
    def width(self) -> float:
        """Ancho normalizado de la caja."""
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        """Alto normalizado de la caja."""
        return self.y_max - self.y_min

    @property
    def center_x(self) -> float:
        """Coordenada X normalizada del centro de la caja."""
        return (self.x_min + self.x_max) / 2

    @property
    def center_y(self) -> float:
        """Coordenada Y normalizada del centro de la caja."""
        return (self.y_min + self.y_max) / 2


@dataclass(frozen=True, slots=True)
class Detection:
    """Un objeto detectado: etiqueta del modelo, confianza y caja."""

    label: str
    confidence: float
    bbox: BoundingBox

    def __post_init__(self) -> None:
        if not self.label:
            msg = "La deteccion requiere una etiqueta no vacia."
            raise ConfigError(msg)
        if not MIN_CONFIDENCE <= self.confidence <= MAX_CONFIDENCE:
            msg = f"La confianza requiere 0 <= confidence <= 1 (llego {self.confidence})."
            raise ConfigError(msg)


def count_by_label(detections: tuple[Detection, ...], *, label: str) -> int:
    """Cuenta las detecciones con esa etiqueta (comparacion exacta)."""
    return sum(1 for detection in detections if detection.label == label)


def count_people(detections: tuple[Detection, ...], *, label: str = PERSON_LABEL) -> int:
    """Cuenta las personas; ``label`` permite apuntar a otra clase del modelo."""
    return count_by_label(detections, label=label)
