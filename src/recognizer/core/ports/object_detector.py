"""Puerto de deteccion generica de objetos."""

from typing import Protocol

from recognizer.core.domain.detection import Detection
from recognizer.core.domain.frame import Frame


class DetectorConfig(Protocol):
    """Parametros minimos que necesita un detector (contador, anti-intrusos...).

    Es estructural: cualquier modelo de configuracion con ``model_path`` y
    ``min_confidence`` sirve, sin acoplar el adaptador a una app concreta.
    """

    model_path: str
    min_confidence: float


class ObjectDetector(Protocol):
    """Detecta objetos sobre fotogramas (YOLO hoy, otro motor en el futuro)."""

    def open(self) -> None:
        """Prepara el detector y carga su modelo."""
        ...

    def detect(self, frame: Frame) -> tuple[Detection, ...]:
        """Detecta los objetos presentes en el fotograma."""
        ...

    def close(self) -> None:
        """Libera los recursos del detector."""
        ...
