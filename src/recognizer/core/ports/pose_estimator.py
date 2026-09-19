"""Puerto de estimacion de postura corporal (keypoints)."""

from typing import Protocol

from recognizer.core.domain.frame import Frame
from recognizer.core.domain.pose import Pose


class PoseEstimatorConfig(Protocol):
    """Parametros minimos que necesita un estimador de pose.

    Es estructural: cualquier modelo de configuracion con ``model_path`` y
    ``min_confidence`` sirve, sin acoplar el adaptador a una app concreta.
    """

    model_path: str
    min_confidence: float


class PoseEstimator(Protocol):
    """Estima los puntos clave de las personas del fotograma."""

    def open(self) -> None:
        """Prepara el estimador y carga su modelo."""
        ...

    def estimate(self, frame: Frame) -> tuple[Pose, ...]:
        """Devuelve las posturas detectadas en el fotograma."""
        ...

    def close(self) -> None:
        """Libera los recursos del estimador."""
        ...
