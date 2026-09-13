"""Puerto de clasificacion de manos y gestos."""

from typing import Protocol

from recognizer.core.domain.frame import Frame
from recognizer.core.domain.gesture import GestureRecognition


class GestureClassifier(Protocol):
    """Clasifica manos y gestos sobre fotogramas (MediaPipe hoy, otro motor futuro)."""

    def open(self) -> None:
        """Prepara el clasificador y carga su modelo."""
        ...

    def classify(self, frame: Frame) -> GestureRecognition:
        """Clasifica las manos y gestos presentes en el fotograma.

        Invariante: ``frame.timestamp`` debe ser monotono creciente entre
        llamadas; el modo VIDEO de MediaPipe usa esos milisegundos para el
        tracking y descarta o falla con marcas de tiempo repetidas o menores.
        """
        ...

    def close(self) -> None:
        """Libera los recursos del clasificador."""
        ...
