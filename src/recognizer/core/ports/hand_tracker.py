"""Puerto de deteccion de manos."""

from typing import Protocol

from recognizer.core.domain.frame import Frame
from recognizer.core.domain.hand import HandLandmarks


class HandTracker(Protocol):
    """Detector de manos sobre fotogramas (MediaPipe hoy, otro motor en el futuro)."""

    def open(self) -> None:
        """Prepara el detector y carga su modelo."""
        ...

    def detect(self, frame: Frame) -> tuple[HandLandmarks, ...]:
        """Detecta las manos presentes en el fotograma.

        Invariante: ``frame.timestamp`` debe ser monotono creciente entre
        llamadas; el modo VIDEO de MediaPipe usa esos milisegundos para el
        tracking y descarta o falla con marcas de tiempo repetidas o menores.
        """
        ...

    def close(self) -> None:
        """Libera los recursos del detector."""
        ...
