"""Puerto de entrada de fotogramas."""

from typing import Protocol

from recognizer.core.domain.frame import Frame


class FrameSource(Protocol):
    """Fuente de fotogramas (camara local hoy, stream web en el futuro)."""

    def open(self) -> None:
        """Prepara la fuente para leer fotogramas."""
        ...

    def read(self) -> Frame | None:
        """Devuelve el siguiente fotograma o None si no esta disponible."""
        ...

    def release(self) -> None:
        """Libera los recursos asociados a la fuente."""
        ...
