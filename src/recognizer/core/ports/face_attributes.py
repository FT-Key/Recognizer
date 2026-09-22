"""Puerto de estimacion de edad y genero por rostro (sin embedding).

Una sola via de inferencia: el mismo detector facial ubica cada rostro y, sobre
su recorte alineado, el modulo de atributos estima edad y genero. No calcula
embeddings ni identidades, y mantiene al adaptador libre de acoplarse a una app
concreta.
"""

from typing import Protocol

from recognizer.core.domain.face_attributes import FaceAttributes
from recognizer.core.domain.frame import Frame


class FaceAttributeEstimatorConfig(Protocol):
    """Parametros minimos que necesita un estimador de atributos.

    Es estructural: cualquier modelo de configuracion con ``model_path``,
    ``min_confidence`` y ``det_size`` sirve. ``det_size`` es el lado de entrada
    del detector (menor = mas rapido en CPU).
    """

    model_path: str
    min_confidence: float
    det_size: int


class FaceAttributeEstimator(Protocol):
    """Estima edad y genero de los rostros del fotograma.

    El ciclo de vida es explicito (``open``/``close``) y admite uso como
    context manager (``with``); los adaptadores implementan ``__enter__`` y
    ``__exit__`` sobre ese ciclo de vida.
    """

    def open(self) -> None:
        """Prepara el estimador y carga su modelo."""
        ...

    def estimate(self, frame: Frame) -> tuple[FaceAttributes, ...]:
        """Devuelve edad y genero de cada rostro (vacio si no hay)."""
        ...

    def close(self) -> None:
        """Libera los recursos del estimador."""
        ...
