"""Despacho de gestos confirmados a acciones locales."""

import logging
from collections.abc import Mapping

from recognizer.core.actions.noop import NoOpAction
from recognizer.core.constants import ACTION_LOGGER_NAME
from recognizer.core.domain.action import Action, ActionContext
from recognizer.core.domain.events import DomainEvent, GestureDetected
from recognizer.core.domain.gesture import GESTURE_NONE, GestureId
from recognizer.core.errors import ActionError


class GestureActionDispatcher:
    """Ejecuta la accion mapeada para cada gesto confirmado."""

    def __init__(
        self,
        *,
        actions: Mapping[GestureId, Action],
        logger: logging.Logger | None = None,
        fallback: Action | None = None,
    ) -> None:
        self._actions = actions
        self._logger = logger or logging.getLogger(ACTION_LOGGER_NAME)
        self._fallback = fallback or NoOpAction()

    def handle(self, event: DomainEvent) -> None:
        """Despacha el evento al mapeo de acciones, si corresponde."""
        match event:
            case GestureDetected(
                gesture=gesture,
                confidence=confidence,
                handedness=handedness,
                timestamp=timestamp,
            ):
                if gesture == GESTURE_NONE:
                    return
                context = ActionContext(
                    gesture=gesture,
                    confidence=confidence,
                    handedness=handedness,
                    timestamp=timestamp,
                )
                try:
                    self._actions.get(gesture, self._fallback).execute(context)
                except ActionError as exc:
                    self._logger.warning("Fallo la accion para %s: %s", gesture.value, exc)
            case _:
                return
