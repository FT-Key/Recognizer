"""Mover del puntero: escucha PointerMoved y delega en el MouseController."""

import logging

from recognizer.core.actions.decorators import ActionGate
from recognizer.core.constants import POINTER_LOGGER_NAME
from recognizer.core.domain.events import DomainEvent, PointerMoved
from recognizer.core.errors import ActionError
from recognizer.core.ports.mouse_controller import MouseController


class PointerMover:
    """Mueve el puntero del sistema ante cada PointerMoved habilitado."""

    def __init__(
        self,
        *,
        controller: MouseController,
        gate: ActionGate | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._controller = controller
        self._gate = gate
        self._logger = logger or logging.getLogger(POINTER_LOGGER_NAME)

    def handle(self, event: DomainEvent) -> None:
        """Mueve el puntero si el gate lo permite y registra los fallos."""
        match event:
            case PointerMoved(x=x, y=y):
                if self._gate is not None and not self._gate.enabled:
                    return
                try:
                    self._controller.move_to(x=x, y=y)
                except ActionError as exc:
                    self._logger.warning("Fallo el movimiento del puntero: %s", exc)
            case _:
                return
