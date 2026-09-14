"""Adaptador de puntero del sistema basado en pynput."""

from collections.abc import Callable
from typing import Protocol, cast

from pynput.mouse import Button, Controller

from recognizer.core.errors import ActionError
from recognizer.core.ports.mouse_controller import MouseController

MIN_SCREEN_EXTENT = 1
PIXEL_INDEX_OFFSET = 1
MIN_NORMALIZED_COORDINATE = 0.0
MAX_NORMALIZED_COORDINATE = 1.0


class PositionController(Protocol):
    """Subconjunto de pynput.mouse.Controller que usamos (permite dobles)."""

    @property
    def position(self) -> tuple[int, int]:
        """Posicion actual del puntero en pixeles."""
        ...

    @position.setter
    def position(self, value: tuple[int, int]) -> None:
        """Mueve el puntero a la posicion indicada."""
        ...

    def click(self, button: Button) -> None:
        """Realiza un click con el boton indicado."""
        ...


def _default_screen_size() -> tuple[int, int]:
    """Obtiene el tamano de pantalla con tkinter (import diferido, solo adaptador)."""
    import tkinter

    try:
        root = tkinter.Tk()
    except tkinter.TclError as exc:
        msg = "No se pudo consultar el tamano de pantalla."
        raise RuntimeError(msg) from exc
    try:
        root.withdraw()
        return (root.winfo_screenwidth(), root.winfo_screenheight())
    finally:
        root.destroy()


def _scale_to_pixels(*, value: float, extent: int) -> int:
    """Escala una coordenada normalizada 0..1 al rango de pixeles disponible."""
    if extent < MIN_SCREEN_EXTENT:
        msg = f"El tamano de pantalla debe ser al menos {MIN_SCREEN_EXTENT} pixel."
        raise ValueError(msg)
    clamped = max(MIN_NORMALIZED_COORDINATE, min(MAX_NORMALIZED_COORDINATE, value))
    return round(clamped * (extent - PIXEL_INDEX_OFFSET))


class PynputMouseController(MouseController):
    """Mueve el puntero del sistema con pynput y cachea el tamano de pantalla."""

    def __init__(
        self,
        *,
        controller: PositionController | None = None,
        screen_size: Callable[[], tuple[int, int]] | None = None,
    ) -> None:
        # pynput no expone stubs: el cast fija la frontera tipada con la libreria.
        self._controller = controller or cast("PositionController", Controller())
        self._screen_size = screen_size or _default_screen_size
        self._cached_screen_size: tuple[int, int] | None = None

    def move_to(self, *, x: float, y: float) -> None:
        """Mueve el puntero a la posicion normalizada indicada.

        Raises:
            ActionError: si no se pudo resolver la pantalla o mover el puntero.
        """
        try:
            width, height = self._resolve_screen_size()
            self._controller.position = (
                _scale_to_pixels(value=x, extent=width),
                _scale_to_pixels(value=y, extent=height),
            )
        except (OSError, ValueError, RuntimeError) as exc:
            msg = "No se pudo mover el puntero."
            raise ActionError(msg) from exc

    def click(self) -> None:
        """Realiza un click izquierdo en la posicion actual del puntero.

        Raises:
            ActionError: si no se pudo realizar el click.
        """
        try:
            self._controller.click(Button.left)
        except (OSError, ValueError) as exc:
            msg = "No se pudo realizar el click."
            raise ActionError(msg) from exc

    def _resolve_screen_size(self) -> tuple[int, int]:
        if self._cached_screen_size is None:
            self._cached_screen_size = self._screen_size()
        return self._cached_screen_size
