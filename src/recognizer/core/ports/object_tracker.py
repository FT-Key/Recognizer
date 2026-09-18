"""Puerto de tracking de objetos con identidad persistente."""

from typing import Protocol

from recognizer.core.domain.frame import Frame
from recognizer.core.domain.tracking import TrackedDetection


class ObjectTracker(Protocol):
    """Sigue objetos entre fotogramas y les asigna un ID de sesion."""

    def open(self) -> None:
        """Prepara el tracker y carga su modelo."""
        ...

    def track(self, frame: Frame) -> tuple[TrackedDetection, ...]:
        """Rastrea los objetos del fotograma y devuelve sus detecciones con ID."""
        ...

    def close(self) -> None:
        """Libera los recursos del tracker."""
        ...
