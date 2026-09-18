"""Tests de la accion de scroll vertical y su configuracion."""

import pytest
from pydantic import ValidationError

from recognizer.core.actions.scroll import ScrollAction
from recognizer.core.config import ActionsConfig, ScrollActionConfig
from recognizer.core.constants import DEFAULT_SCROLL_LINES, DEFAULT_SCROLL_REPEAT_SECONDS
from recognizer.core.domain.action import ActionContext
from recognizer.core.domain.gesture import GESTURE_VICTORY
from recognizer.core.domain.hand import Handedness
from recognizer.core.domain.pointer import ScrollDirection
from recognizer.core.errors import ConfigError

SCROLL_LINES = 3
EVENT_TIMESTAMP = 1.0
GESTURE_CONFIDENCE = 0.8


class RecordingMouseController:
    """Doble de MouseController que registra los desplazamientos recibidos."""

    def __init__(self) -> None:
        self.scrolls: list[tuple[int, int]] = []

    def move_to(self, *, x: float, y: float) -> None:
        del x, y

    def click(self) -> None:
        pass

    def scroll_by(self, *, dx: int, dy: int) -> None:
        self.scrolls.append((dx, dy))


def _context() -> ActionContext:
    return ActionContext(
        gesture=GESTURE_VICTORY,
        confidence=GESTURE_CONFIDENCE,
        handedness=Handedness.RIGHT,
        timestamp=EVENT_TIMESTAMP,
    )


def test_scroll_up_calls_scroll_by_with_positive_lines() -> None:
    controller = RecordingMouseController()
    action = ScrollAction(
        direction=ScrollDirection.UP,
        lines=SCROLL_LINES,
        controller=controller,
    )

    action.execute(_context())

    assert controller.scrolls == [(0, SCROLL_LINES)]


def test_scroll_down_calls_scroll_by_with_negative_lines() -> None:
    controller = RecordingMouseController()
    action = ScrollAction(
        direction=ScrollDirection.DOWN,
        lines=SCROLL_LINES,
        controller=controller,
    )

    action.execute(_context())

    assert controller.scrolls == [(0, -SCROLL_LINES)]


@pytest.mark.parametrize("lines", [0, -1, -10])
def test_scroll_lines_below_minimum_are_rejected(lines: int) -> None:
    with pytest.raises(ConfigError, match="lines"):
        ScrollAction(
            direction=ScrollDirection.UP,
            lines=lines,
            controller=RecordingMouseController(),
        )


def test_scroll_config_defaults() -> None:
    config = ScrollActionConfig(direction=ScrollDirection.UP)

    assert config.type == "scroll"
    assert config.direction is ScrollDirection.UP
    assert config.lines == DEFAULT_SCROLL_LINES
    assert config.repeat_seconds == DEFAULT_SCROLL_REPEAT_SECONDS
    assert config.cooldown_seconds is None


def test_scroll_config_rejects_lines_below_one() -> None:
    with pytest.raises(ValidationError):
        ScrollActionConfig(direction=ScrollDirection.DOWN, lines=0)


def test_scroll_config_parses_through_discriminated_union() -> None:
    config = ActionsConfig.model_validate(
        {
            "mappings": {
                "Victory": {
                    "type": "scroll",
                    "direction": "up",
                    "lines": 3,
                    "repeat_seconds": 0.15,
                    "cooldown_seconds": 0.12,
                }
            }
        }
    )

    action = config.mappings["Victory"]
    assert isinstance(action, ScrollActionConfig)
    assert action.direction is ScrollDirection.UP
    assert action.lines == 3
    assert action.repeat_seconds == 0.15
    assert action.cooldown_seconds == 0.12
