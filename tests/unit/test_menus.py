"""Tests de los gestos compuestos: tracker por mano y resolucion de menus."""

import pytest

from recognizer.core.actions.menus import (
    HandGestureTracker,
    Menu,
    MenuMatch,
    find_menu_match,
    other_hand,
)
from recognizer.core.domain.action import Action, ActionContext
from recognizer.core.domain.gesture import (
    GESTURE_NONE,
    GESTURE_OPEN_PALM,
    GESTURE_POINTING_UP,
    GESTURE_VICTORY,
    GestureId,
)
from recognizer.core.domain.hand import Handedness


class RecordingAction:
    """Doble de Action que acumula los contextos ejecutados."""

    def __init__(self) -> None:
        self.contexts: list[ActionContext] = []

    def execute(self, context: ActionContext) -> None:
        self.contexts.append(context)


def _menu(
    *,
    name: str = "Replay",
    hand: Handedness = Handedness.LEFT,
    modifier: GestureId = GESTURE_POINTING_UP,
    consume_trigger: bool = True,
    options: dict[GestureId, Action] | None = None,
) -> Menu:
    return Menu(
        name=name,
        hand=hand,
        modifier=modifier,
        consume_trigger=consume_trigger,
        options=options if options is not None else {GESTURE_VICTORY: RecordingAction()},
    )


@pytest.mark.parametrize(
    ("hand", "expected"),
    [
        (Handedness.LEFT, Handedness.RIGHT),
        (Handedness.RIGHT, Handedness.LEFT),
        (Handedness.UNKNOWN, Handedness.UNKNOWN),
    ],
)
def test_other_hand_swaps_laterality(hand: Handedness, expected: Handedness) -> None:
    assert other_hand(hand) is expected


def test_tracker_returns_none_before_observation() -> None:
    tracker = HandGestureTracker()

    assert tracker.current(Handedness.LEFT) is None


def test_tracker_observe_and_release_by_hand() -> None:
    tracker = HandGestureTracker()
    tracker.observe(Handedness.LEFT, GESTURE_POINTING_UP)
    tracker.observe(Handedness.RIGHT, GESTURE_VICTORY)

    assert tracker.current(Handedness.LEFT) == GESTURE_POINTING_UP
    assert tracker.current(Handedness.RIGHT) == GESTURE_VICTORY

    tracker.release(Handedness.LEFT)

    assert tracker.current(Handedness.LEFT) is None
    assert tracker.current(Handedness.RIGHT) == GESTURE_VICTORY


def test_tracker_release_unknown_hand_is_noop() -> None:
    tracker = HandGestureTracker()

    tracker.release(Handedness.LEFT)

    assert tracker.current(Handedness.LEFT) is None


def test_find_menu_match_with_modifier_and_option() -> None:
    action = RecordingAction()
    menu = _menu(options={GESTURE_VICTORY: action})
    tracker = HandGestureTracker()
    tracker.observe(Handedness.LEFT, GESTURE_POINTING_UP)
    tracker.observe(Handedness.RIGHT, GESTURE_VICTORY)

    match = find_menu_match(menus=[menu], tracker=tracker)

    assert match == MenuMatch(menu=menu, trigger=GESTURE_VICTORY, action=action)


def test_find_menu_match_is_order_independent() -> None:
    action = RecordingAction()
    menu = _menu(options={GESTURE_VICTORY: action})
    tracker = HandGestureTracker()
    tracker.observe(Handedness.RIGHT, GESTURE_VICTORY)
    tracker.observe(Handedness.LEFT, GESTURE_POINTING_UP)

    match = find_menu_match(menus=[menu], tracker=tracker)

    assert match is not None
    assert match.trigger == GESTURE_VICTORY
    assert match.action is action


def test_find_menu_match_without_modifier_returns_none() -> None:
    menu = _menu(options={GESTURE_VICTORY: RecordingAction()})
    tracker = HandGestureTracker()
    tracker.observe(Handedness.RIGHT, GESTURE_VICTORY)

    assert find_menu_match(menus=[menu], tracker=tracker) is None


def test_find_menu_match_without_option_returns_none() -> None:
    menu = _menu(options={GESTURE_VICTORY: RecordingAction()})
    tracker = HandGestureTracker()
    tracker.observe(Handedness.LEFT, GESTURE_POINTING_UP)
    tracker.observe(Handedness.RIGHT, GESTURE_OPEN_PALM)

    assert find_menu_match(menus=[menu], tracker=tracker) is None


def test_find_menu_match_none_gesture_does_not_match() -> None:
    menu = _menu(options={GESTURE_VICTORY: RecordingAction()})
    tracker = HandGestureTracker()
    tracker.observe(Handedness.LEFT, GESTURE_POINTING_UP)
    tracker.observe(Handedness.RIGHT, GESTURE_NONE)

    assert find_menu_match(menus=[menu], tracker=tracker) is None


def test_find_menu_match_returns_first_matching_menu() -> None:
    first_action = RecordingAction()
    second_action = RecordingAction()
    first = _menu(name="Primero", options={GESTURE_VICTORY: first_action})
    second = _menu(name="Segundo", options={GESTURE_VICTORY: second_action})
    tracker = HandGestureTracker()
    tracker.observe(Handedness.LEFT, GESTURE_POINTING_UP)
    tracker.observe(Handedness.RIGHT, GESTURE_VICTORY)

    match = find_menu_match(menus=[first, second], tracker=tracker)

    assert match is not None
    assert match.menu is first
    assert match.action is first_action


def test_find_menu_match_skips_menu_with_inactive_modifier() -> None:
    second_action = RecordingAction()
    inactive = _menu(
        name="Inactivo",
        modifier=GESTURE_OPEN_PALM,
        options={GESTURE_VICTORY: RecordingAction()},
    )
    active = _menu(name="Activo", options={GESTURE_VICTORY: second_action})
    tracker = HandGestureTracker()
    tracker.observe(Handedness.LEFT, GESTURE_POINTING_UP)
    tracker.observe(Handedness.RIGHT, GESTURE_VICTORY)

    match = find_menu_match(menus=[inactive, active], tracker=tracker)

    assert match is not None
    assert match.menu is active
    assert match.action is second_action
