"""Puerto de reconocimiento facial (deteccion + embedding)."""

from typing import Protocol

from recognizer.core.domain.face import FaceObservation
from recognizer.core.domain.frame import Frame


class FaceRecognizerConfig(Protocol):
    """Parametros minimos que necesita un reconocedor facial.

    Es estructural: cualquier modelo de configuracion con ``model_path``,
    ``min_confidence`` y ``det_size`` sirve, sin acoplar el adaptador a una app
    concreta. ``det_size`` es el lado de entrada del detector (menor = más
    rápido en CPU, útil con cámaras de red o del teléfono).
    """

    model_path: str
    min_confidence: float
    det_size: int


class FaceRecognizer(Protocol):
    """Detecta rostros en el fotograma y extrae su embedding normalizado.

    El ciclo de vida es explicito (``open``/``close``) y admite uso como
    context manager (``with``); los adaptadores implementan ``__enter__`` y
    ``__exit__`` sobre ese ciclo de vida.
    """

    def open(self) -> None:
        """Prepara el reconocedor y carga su modelo."""
        ...

    def recognize(self, frame: Frame) -> tuple[FaceObservation, ...]:
        """Devuelve las caras observadas en el fotograma (vacio si no hay)."""
        ...

    def close(self) -> None:
        """Libera los recursos del reconocedor."""
        ...
