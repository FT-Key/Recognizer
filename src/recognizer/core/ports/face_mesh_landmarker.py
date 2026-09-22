"""Puerto de deteccion de landmarks faciales (468 puntos Face Mesh).

Una sola via de inferencia: el mismo modelo MediaPipe Face Mesh detecta
rostros y devuelve 468 landmarks 3D por rostro. Permite calcular EAR
(Eye Aspect Ratio), MAR (Mouth Aspect Ratio) y otros ratios faciales
para deteccion de somnolencia, parpadeo y bostezos.
"""

from typing import Protocol

from recognizer.core.domain.face_landmarks import FaceMeshResult
from recognizer.core.domain.frame import Frame


class FaceMeshConfig(Protocol):
    """Parametros minimos que necesita un landmark facial.

    Es estructural: cualquier modelo de configuracion con ``model_path``,
    ``min_face_detection_confidence`` y ``min_face_presence_confidence``
    sirve.
    """

    model_path: str
    min_face_detection_confidence: float
    min_face_presence_confidence: float


class FaceMeshLandmarker(Protocol):
    """Detecta landmarks faciales (468 puntos) en el fotograma.

    El ciclo de vida es explicito (``open``/``close``) y admite uso como
    context manager (``with``); los adaptadores implementan ``__enter__`` y
    ``__exit__`` sobre ese ciclo de vida.
    """

    def open(self) -> None:
        """Prepara el landmarker y carga su modelo."""
        ...

    def detect(self, frame: Frame) -> tuple[FaceMeshResult, ...]:
        """Devuelve los landmarks de cada rostro detectado (vacio si no hay)."""
        ...

    def close(self) -> None:
        """Libera los recursos del landmarker."""
        ...
