"""Accion de scroll vertical delegada en el puerto del raton."""

from recognizer.core.constants import MIN_SCROLL_LINES, SCROLL_FIXED_AXIS
from recognizer.core.domain.action import Action, ActionContext
from recognizer.core.domain.pointer import ScrollDirection
from recognizer.core.errors import ConfigError
from recognizer.core.ports.mouse_controller import MouseController


class ScrollAction(Action):
    """Desplaza la rueda del raton ante un gesto sostenido."""

    def __init__(
        self,
        *,
        direction: ScrollDirection,
        lines: int,
        controller: MouseController,
    ) -> None:
        if lines < MIN_SCROLL_LINES:
            msg = f"ScrollAction requiere lines >= {MIN_SCROLL_LINES}."
            raise ConfigError(msg)
        self._direction = direction
        self._lines = lines
        self._controller = controller

    def execute(self, context: ActionContext) -> None:
        """Desplaza arriba (dy positivo) o abajo (dy negativo)."""
        del context
        delta = self._lines if self._direction is ScrollDirection.UP else -self._lines
        self._controller.scroll_by(dx=SCROLL_FIXED_AXIS, dy=delta)
