"""Decoradores de acciones: log, debounce y gate."""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from recognizer.core.constants import ACTION_LOGGER_NAME
from recognizer.core.domain.action import Action, ActionContext


@dataclass(slots=True)
class ActionGate:
    """Interruptor compartido que habilita o deshabilita acciones."""

    enabled: bool = True

    def toggle(self) -> bool:
        """Invierte el estado y devuelve el valor nuevo."""
        self.enabled = not self.enabled
        return self.enabled


class LoggedAction(Action):
    """Registra cada ejecucion antes de delegar en la accion envuelta."""

    def __init__(self, action: Action, *, logger: logging.Logger | None = None) -> None:
        self._action = action
        self._logger = logger or logging.getLogger(ACTION_LOGGER_NAME)

    def execute(self, context: ActionContext) -> None:
        """Loguea el gesto y delega en la accion envuelta."""
        self._logger.info(
            "Ejecutando %s para gesto %s",
            type(self._action).__name__,
            context.gesture.value,
        )
        self._action.execute(context)


class DebouncedAction(Action):
    """Ignora ejecuciones repetidas dentro del cooldown configurado."""

    def __init__(
        self,
        action: Action,
        *,
        cooldown_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._action = action
        self._cooldown_seconds = cooldown_seconds
        self._clock = clock
        self._last_execution: float | None = None

    def execute(self, context: ActionContext) -> None:
        """Delega solo si transcurrio el cooldown desde la ultima ejecucion."""
        now = self._clock()
        if self._last_execution is not None and now - self._last_execution < self._cooldown_seconds:
            return
        self._last_execution = now
        self._action.execute(context)


class GatedAction(Action):
    """Ejecuta la accion solo cuando el gate compartido esta habilitado."""

    def __init__(self, action: Action, *, gate: ActionGate) -> None:
        self._action = action
        self._gate = gate

    @property
    def enabled(self) -> bool:
        """Indica si el gate permite ejecutar la accion."""
        return self._gate.enabled

    def execute(self, context: ActionContext) -> None:
        """Delega si el gate esta habilitado; si no, ignora la ejecucion."""
        if self._gate.enabled:
            self._action.execute(context)
