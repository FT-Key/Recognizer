"""Menus compuestos: una mano sostiene el modificador y la otra elige.

El estado vive en ``HandGestureTracker`` (core puro, sin efectos); el dispatcher
lo alimenta con los eventos confirmados de cada mano y resuelve la opcion activa
con ``find_menu_match``.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from recognizer.core.domain.action import Action
from recognizer.core.domain.gesture import GestureId
from recognizer.core.domain.hand import Handedness, other_hand

__all__ = ["HandGestureTracker", "Menu", "MenuMatch", "find_menu_match", "other_hand"]


@dataclass(frozen=True, slots=True)
class Menu:
    """Lista de opciones que se activa con un gesto modificador de una mano."""

    name: str
    hand: Handedness
    modifier: GestureId
    consume_trigger: bool
    options: Mapping[GestureId, Action]


@dataclass(frozen=True, slots=True)
class MenuMatch:
    """Menu, gesto disparador y accion resueltos para una ejecucion."""

    menu: Menu
    trigger: GestureId
    action: Action


class HandGestureTracker:
    """Recuerda el ultimo gesto confirmado de cada mano."""

    def __init__(self) -> None:
        self._current: dict[Handedness, GestureId] = {}

    def observe(self, handedness: Handedness, gesture: GestureId) -> None:
        """Registra el gesto actual de una mano."""
        self._current[handedness] = gesture

    def release(self, handedness: Handedness) -> None:
        """Olvida el gesto de una mano."""
        self._current.pop(handedness, None)

    def current(self, handedness: Handedness) -> GestureId | None:
        """Devuelve el gesto actual de una mano, o ``None`` si no hay."""
        return self._current.get(handedness)


def find_menu_match(
    *,
    menus: Sequence[Menu],
    tracker: HandGestureTracker,
) -> MenuMatch | None:
    """Resuelve el primer menu cuyo modificador y opcion esten activos.

    No muta el tracker: solo consulta el estado por mano.
    """
    for menu in menus:
        if tracker.current(menu.hand) != menu.modifier:
            continue
        trigger = tracker.current(other_hand(menu.hand))
        if trigger is None or trigger not in menu.options:
            continue
        return MenuMatch(menu=menu, trigger=trigger, action=menu.options[trigger])
    return None
