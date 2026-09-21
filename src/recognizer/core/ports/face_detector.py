"""Puerto de deteccion facial (solo cajas, sin embedding).

La app de desenfoque de privacidad solo necesita ubicar rostros para
difuminarlos; este puerto evita calcular embeddings y mantiene el adaptador
libre de acoplarse a una app concreta.
"""

from typing import Protocol

from recognizer.core.domain.face import FaceBox
from recognizer.core.domain.frame import Frame


class FaceDetectorConfig(Protocol):
    """Parametros minimos que necesita un detector facial.

    Es estructural: cualquier modelo de configuracion con ``model_path``,
    ``min_confidence`` y ``det_size`` sirve. ``det_size`` es el lado de entrada
    del detector (menor = mas rapido en CPU).
    """

    model_path: str
    min_confidence: float
    det_size: int


class FaceDetector(Protocol):
    """Detecta rostros en el fotograma y devuelve sus cajas normalizadas.

    El ciclo de vida es explicito (``open``/``close``) y admite uso como
    context manager (``with``); los adaptadores implementan ``__enter__`` y
    ``__exit__`` sobre ese ciclo de vida.
    """

    def open(self) -> None:
        """Prepara el detector y carga su modelo."""
        ...

    def detect(self, frame: Frame) -> tuple[FaceBox, ...]:
        """Devuelve las cajas de los rostros del fotograma (vacio si no hay)."""
        ...

    def close(self) -> None:
        """Libera los recursos del detector."""
        ...
