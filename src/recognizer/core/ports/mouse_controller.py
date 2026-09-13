"""Puerto de control del puntero del sistema."""

from typing import Protocol


class MouseController(Protocol):
    """Mueve el puntero del sistema anfitrion."""

    def move_to(self, *, x: float, y: float) -> None:
        """Mueve el puntero a la posicion normalizada (0..1); el adaptador recorta."""
        ...
