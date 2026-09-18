"""Tests del despachador de gestos confirmados a acciones locales."""

import logging

import pytest

from recognizer.core.actions.dispatcher import GestureActionDispatcher
from recognizer.core.actions.menus import Menu
from recognizer.core.constants import ACTION_LOGGER_NAME
from recognizer.core.domain.action import Action, ActionContext
from recognizer.core.domain.events import (
    DomainEvent,
    GestureDetected,
    GestureHeld,
    GestureReleased,
    HandsDetected,
)
from recognizer.core.domain.gesture import (
    GESTURE_NONE,
    GESTURE_OPEN_PALM,
    GESTURE_POINTING_UP,
    GESTURE_THUMB_UP,
    GESTURE_VICTORY,
    GestureId,
)
from recognizer.core.domain.hand import Handedness
from recognizer.core.errors import ActionError

GESTURE_CONFIDENCE = 0.8
TIMESTAMP = 1.0


class RecordingAction:
    """Doble de Action que acumula los contextos ejecutados."""

    def __init__(self) -> None:
        self.contexts: list[ActionContext] = []

    def execute(self, context: ActionContext) -> None:
        self.contexts.append(context)


class FailingAction:
    """Doble de Action que siempre falla con ActionError."""

    def execute(self, context: ActionContext) -> None:
        del context
        msg = "fallo simulado"
        raise ActionError(msg)


class CrashingAction:
    """Doble de Action que falla con un error inesperado (no ActionError)."""

    def execute(self, context: ActionContext) -> None:
        del context
        msg = "crash inesperado"
        raise ModuleNotFoundError(msg)


def _detected(
    gesture: GestureId = GESTURE_VICTORY,
    *,
    confidence: float = GESTURE_CONFIDENCE,
    handedness: Handedness = Handedness.RIGHT,
) -> GestureDetected:
    return GestureDetected(
        timestamp=TIMESTAMP,
        gesture=gesture,
        confidence=confidence,
        handedness=handedness,
    )


def _menu(
    *,
    action: Action,
    hand: Handedness = Handedness.LEFT,
    modifier: GestureId = GESTURE_POINTING_UP,
    consume_trigger: bool = True,
    trigger: GestureId = GESTURE_VICTORY,
) -> Menu:
    return Menu(
        name="Replay",
        hand=hand,
        modifier=modifier,
        consume_trigger=consume_trigger,
        options={trigger: action},
    )


def test_mapped_gesture_executes_with_context() -> None:
    action = RecordingAction()
    dispatcher = GestureActionDispatcher(actions={GESTURE_VICTORY: action})

    dispatcher.handle(_detected())

    assert action.contexts == [
        ActionContext(
            gesture=GESTURE_VICTORY,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.RIGHT,
            timestamp=TIMESTAMP,
        )
    ]


def test_unmapped_gesture_does_not_raise_with_default_fallback() -> None:
    dispatcher = GestureActionDispatcher(actions={GESTURE_VICTORY: RecordingAction()})

    dispatcher.handle(_detected(GESTURE_OPEN_PALM))


def test_unmapped_gesture_uses_injected_fallback() -> None:
    fallback = RecordingAction()
    dispatcher = GestureActionDispatcher(actions={}, fallback=fallback)

    dispatcher.handle(_detected(GESTURE_OPEN_PALM))

    assert len(fallback.contexts) == 1
    assert fallback.contexts[0].gesture is GESTURE_OPEN_PALM


def test_none_gesture_is_ignored() -> None:
    fallback = RecordingAction()
    dispatcher = GestureActionDispatcher(actions={}, fallback=fallback)

    dispatcher.handle(_detected(GESTURE_NONE))

    assert fallback.contexts == []


@pytest.mark.parametrize(
    "event",
    [
        GestureReleased(
            timestamp=TIMESTAMP,
            gesture=GESTURE_VICTORY,
            handedness=Handedness.RIGHT,
        ),
        HandsDetected(timestamp=TIMESTAMP, hands=()),
    ],
)
def test_other_events_are_ignored(event: DomainEvent) -> None:
    fallback = RecordingAction()
    dispatcher = GestureActionDispatcher(actions={}, fallback=fallback)

    dispatcher.handle(event)

    assert fallback.contexts == []


def test_action_error_is_logged_as_warning_and_not_propagated(
    caplog: pytest.LogCaptureFixture,
) -> None:
    dispatcher = GestureActionDispatcher(actions={GESTURE_VICTORY: FailingAction()})

    with caplog.at_level(logging.WARNING, logger=ACTION_LOGGER_NAME):
        dispatcher.handle(_detected())

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == logging.WARNING
    assert record.name == ACTION_LOGGER_NAME
    assert GESTURE_VICTORY.value in record.getMessage()


def test_unexpected_action_error_is_logged_and_not_propagated(
    caplog: pytest.LogCaptureFixture,
) -> None:
    dispatcher = GestureActionDispatcher(actions={GESTURE_VICTORY: CrashingAction()})

    with caplog.at_level(logging.ERROR, logger=ACTION_LOGGER_NAME):
        dispatcher.handle(_detected())

    assert any(record.levelno == logging.ERROR for record in caplog.records)
    assert any("inesperado" in record.getMessage().lower() for record in caplog.records)


def test_menu_executes_option_and_consumes_global_trigger() -> None:
    menu_action = RecordingAction()
    global_victory = RecordingAction()
    menu = _menu(action=menu_action)
    dispatcher = GestureActionDispatcher(
        actions={GESTURE_VICTORY: global_victory},
        menus=[menu],
    )

    dispatcher.handle(_detected(GESTURE_POINTING_UP, handedness=Handedness.LEFT))
    dispatcher.handle(_detected(GESTURE_VICTORY))

    assert len(menu_action.contexts) == 1
    assert menu_action.contexts[0].gesture is GESTURE_VICTORY
    assert menu_action.contexts[0].handedness is Handedness.RIGHT
    assert global_victory.contexts == []


def test_menu_does_not_repeat_until_option_is_released() -> None:
    menu_action = RecordingAction()
    menu = _menu(action=menu_action)
    dispatcher = GestureActionDispatcher(actions={}, menus=[menu])

    dispatcher.handle(_detected(GESTURE_POINTING_UP, handedness=Handedness.LEFT))
    dispatcher.handle(_detected(GESTURE_VICTORY))
    dispatcher.handle(_detected(GESTURE_VICTORY))
    dispatcher.handle(_detected(GESTURE_VICTORY))

    assert len(menu_action.contexts) == 1

    dispatcher.handle(
        GestureReleased(
            timestamp=TIMESTAMP,
            gesture=GESTURE_VICTORY,
            handedness=Handedness.RIGHT,
        )
    )
    dispatcher.handle(_detected(GESTURE_VICTORY))

    assert len(menu_action.contexts) == 2


def test_menu_does_not_repeat_when_modifier_flickers() -> None:
    menu_action = RecordingAction()
    menu = _menu(action=menu_action)
    dispatcher = GestureActionDispatcher(actions={}, menus=[menu])

    dispatcher.handle(_detected(GESTURE_POINTING_UP, handedness=Handedness.LEFT))
    dispatcher.handle(_detected(GESTURE_VICTORY))
    dispatcher.handle(
        GestureReleased(
            timestamp=TIMESTAMP,
            gesture=GESTURE_POINTING_UP,
            handedness=Handedness.LEFT,
        )
    )
    dispatcher.handle(_detected(GESTURE_POINTING_UP, handedness=Handedness.LEFT))

    assert len(menu_action.contexts) == 1

    dispatcher.handle(
        GestureReleased(
            timestamp=TIMESTAMP,
            gesture=GESTURE_VICTORY,
            handedness=Handedness.RIGHT,
        )
    )
    dispatcher.handle(_detected(GESTURE_POINTING_UP, handedness=Handedness.LEFT))
    dispatcher.handle(_detected(GESTURE_VICTORY))

    assert len(menu_action.contexts) == 2


def test_menu_without_consume_trigger_still_runs_global_action() -> None:
    menu_action = RecordingAction()
    global_victory = RecordingAction()
    menu = _menu(action=menu_action, consume_trigger=False)
    dispatcher = GestureActionDispatcher(
        actions={GESTURE_VICTORY: global_victory},
        menus=[menu],
    )

    dispatcher.handle(_detected(GESTURE_POINTING_UP, handedness=Handedness.LEFT))
    dispatcher.handle(_detected(GESTURE_VICTORY))

    assert len(menu_action.contexts) == 1
    assert len(global_victory.contexts) == 1
    assert global_victory.contexts[0].gesture is GESTURE_VICTORY


def test_single_hand_runs_global_mapping_with_menus_configured() -> None:
    menu_action = RecordingAction()
    global_victory = RecordingAction()
    menu = _menu(action=menu_action)
    dispatcher = GestureActionDispatcher(
        actions={GESTURE_VICTORY: global_victory},
        menus=[menu],
    )

    dispatcher.handle(_detected(GESTURE_VICTORY))

    assert menu_action.contexts == []
    assert len(global_victory.contexts) == 1


def test_menu_modifier_suppresses_global_action_for_non_option_gesture() -> None:
    global_thumb = RecordingAction()
    menu = _menu(action=RecordingAction())
    dispatcher = GestureActionDispatcher(
        actions={GESTURE_THUMB_UP: global_thumb},
        menus=[menu],
    )

    dispatcher.handle(_detected(GESTURE_POINTING_UP, handedness=Handedness.LEFT))
    dispatcher.handle(_detected(GESTURE_THUMB_UP))

    assert global_thumb.contexts == []


def test_menu_modifier_releases_global_action_after_modifier_release() -> None:
    global_thumb = RecordingAction()
    menu = _menu(action=RecordingAction())
    dispatcher = GestureActionDispatcher(
        actions={GESTURE_THUMB_UP: global_thumb},
        menus=[menu],
    )

    dispatcher.handle(_detected(GESTURE_POINTING_UP, handedness=Handedness.LEFT))
    dispatcher.handle(
        GestureReleased(
            timestamp=TIMESTAMP,
            gesture=GESTURE_POINTING_UP,
            handedness=Handedness.LEFT,
        )
    )
    dispatcher.handle(_detected(GESTURE_THUMB_UP))

    assert len(global_thumb.contexts) == 1


def _held(
    gesture: GestureId = GESTURE_VICTORY,
    *,
    confidence: float = GESTURE_CONFIDENCE,
    handedness: Handedness = Handedness.RIGHT,
) -> GestureHeld:
    return GestureHeld(
        timestamp=TIMESTAMP,
        gesture=gesture,
        confidence=confidence,
        handedness=handedness,
    )


def test_held_without_menus_runs_global_action() -> None:
    global_victory = RecordingAction()
    dispatcher = GestureActionDispatcher(actions={GESTURE_VICTORY: global_victory})

    dispatcher.handle(_held(GESTURE_VICTORY))

    assert len(global_victory.contexts) == 1
    assert global_victory.contexts[0].gesture is GESTURE_VICTORY


def test_held_none_is_ignored() -> None:
    fallback = RecordingAction()
    dispatcher = GestureActionDispatcher(actions={}, fallback=fallback)

    dispatcher.handle(_held(GESTURE_NONE))

    assert fallback.contexts == []


def test_held_with_active_menu_consumes_global_trigger() -> None:
    menu_action = RecordingAction()
    global_victory = RecordingAction()
    dispatcher = GestureActionDispatcher(
        actions={GESTURE_VICTORY: global_victory},
        menus=[_menu(action=menu_action)],
    )

    dispatcher.handle(_detected(GESTURE_POINTING_UP, handedness=Handedness.LEFT))
    dispatcher.handle(_detected(GESTURE_VICTORY))
    assert len(menu_action.contexts) == 1
    assert global_victory.contexts == []

    dispatcher.handle(_held(GESTURE_VICTORY))

    assert len(menu_action.contexts) == 1
    assert global_victory.contexts == []


def test_held_with_modifier_held_but_no_match_suppresses_global() -> None:
    global_thumb = RecordingAction()
    dispatcher = GestureActionDispatcher(
        actions={GESTURE_THUMB_UP: global_thumb},
        menus=[_menu(action=RecordingAction())],
    )

    dispatcher.handle(_detected(GESTURE_POINTING_UP, handedness=Handedness.LEFT))
    dispatcher.handle(_held(GESTURE_THUMB_UP))

    assert global_thumb.contexts == []


def test_menu_option_action_error_is_logged_and_not_propagated(
    caplog: pytest.LogCaptureFixture,
) -> None:
    menu = _menu(action=FailingAction())
    dispatcher = GestureActionDispatcher(actions={}, menus=[menu])
    dispatcher.handle(_detected(GESTURE_POINTING_UP, handedness=Handedness.LEFT))

    with caplog.at_level(logging.WARNING, logger=ACTION_LOGGER_NAME):
        dispatcher.handle(_detected(GESTURE_VICTORY))

    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.WARNING
