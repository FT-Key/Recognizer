"""Despacho de gestos confirmados a acciones locales y menus compuestos."""

import logging
from collections.abc import Mapping, Sequence

from recognizer.core.actions.menus import (
    HandGestureTracker,
    Menu,
    MenuMatch,
    find_menu_match,
    modifier_is_held,
    other_hand,
)
from recognizer.core.actions.noop import NoOpAction
from recognizer.core.constants import ACTION_LOGGER_NAME
from recognizer.core.domain.action import Action, ActionContext
from recognizer.core.domain.events import DomainEvent, GestureDetected, GestureReleased
from recognizer.core.domain.gesture import GESTURE_NONE, GestureId
from recognizer.core.domain.hand import Handedness
from recognizer.core.errors import ActionError


class GestureActionDispatcher:
    """Ejecuta acciones de menus compuestos y del mapeo global de gestos."""

    def __init__(
        self,
        *,
        actions: Mapping[GestureId, Action],
        menus: Sequence[Menu] = (),
        logger: logging.Logger | None = None,
        fallback: Action | None = None,
    ) -> None:
        self._actions = actions
        self._menus = tuple(menus)
        self._logger = logger or logging.getLogger(ACTION_LOGGER_NAME)
        self._fallback = fallback or NoOpAction()
        self._tracker = HandGestureTracker()
        self._last_match: tuple[Handedness, str, GestureId] | None = None

    def handle(self, event: DomainEvent) -> None:
        """Despacha el evento al menu activo o al mapeo global, si corresponde."""
        match event:
            case GestureDetected(
                gesture=gesture,
                confidence=confidence,
                handedness=handedness,
                timestamp=timestamp,
            ):
                if gesture == GESTURE_NONE:
                    return
                self._tracker.observe(handedness, gesture)
                found = find_menu_match(menus=self._menus, tracker=self._tracker)
                if found is None:
                    if modifier_is_held(menus=self._menus, tracker=self._tracker):
                        return
                    self._run_global(
                        gesture=gesture,
                        confidence=confidence,
                        handedness=handedness,
                        timestamp=timestamp,
                    )
                    return
                self._run_menu_match(
                    found=found,
                    confidence=confidence,
                    timestamp=timestamp,
                )
                if found.menu.consume_trigger:
                    return
                self._run_global(
                    gesture=gesture,
                    confidence=confidence,
                    handedness=handedness,
                    timestamp=timestamp,
                )
            case GestureReleased(handedness=handedness):
                self._tracker.release(handedness)
                if self._last_match is not None and self._last_match[0] == handedness:
                    self._last_match = None
            case _:
                return

    def _run_menu_match(
        self,
        *,
        found: MenuMatch,
        confidence: float,
        timestamp: float,
    ) -> None:
        trigger_hand = other_hand(found.menu.hand)
        key = (trigger_hand, found.menu.name, found.trigger)
        if key == self._last_match:
            return
        context = ActionContext(
            gesture=found.trigger,
            confidence=confidence,
            handedness=trigger_hand,
            timestamp=timestamp,
        )
        self._execute(action=found.action, context=context)
        self._last_match = key

    def _run_global(
        self,
        *,
        gesture: GestureId,
        confidence: float,
        handedness: Handedness,
        timestamp: float,
    ) -> None:
        context = ActionContext(
            gesture=gesture,
            confidence=confidence,
            handedness=handedness,
            timestamp=timestamp,
        )
        self._execute(action=self._actions.get(gesture, self._fallback), context=context)

    def _execute(self, *, action: Action, context: ActionContext) -> None:
        try:
            action.execute(context)
        except ActionError as exc:
            self._logger.warning("Fallo la accion para %s: %s", context.gesture.value, exc)
