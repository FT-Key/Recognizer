"""Handler del puntero: escucha PointerClicked y delega en MouseController."""

import logging

from recognizer.core.actions.decorators import ActionGate
from recognizer.core.constants import POINTER_LOGGER_NAME
from recognizer.core.domain.events import DomainEvent, PointerClicked
from recognizer.core.errors import ActionError
from recognizer.core.ports.mouse_controller import MouseController


class PointerClicker:
    """Ejecuta un click izquierdo ante cada PointerClicked habilitado."""

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
        """Realiza click si el gate lo permite y registra los fallos."""
        match event:
            case PointerClicked():
                if self._gate is not None and not self._gate.enabled:
                    return
                try:
                    self._controller.click()
                except ActionError as exc:
                    self._logger.warning("Fallo el click del puntero: %s", exc)
            case _:
                return
