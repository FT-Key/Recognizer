"""Tests de la accion que abre enlaces en orden secuencial y rotatorio."""

import pytest

from recognizer.core.actions.links import OpenLinksAction
from recognizer.core.domain.action import ActionContext
from recognizer.core.domain.gesture import GESTURE_VICTORY
from recognizer.core.domain.hand import Handedness
from recognizer.core.errors import ActionError, ConfigError

URLS = (
    "https://primero.example",
    "https://segundo.example",
    "https://tercero.example",
)
GESTURE_CONFIDENCE = 0.85
TIMESTAMP = 3.5


class RecordingLinkOpener:
    """Doble de LinkOpener que registra las URLs abiertas."""

    def __init__(self) -> None:
        self.urls: list[str] = []

    def open(self, url: str) -> None:
        self.urls.append(url)


def _context() -> ActionContext:
    return ActionContext(
        gesture=GESTURE_VICTORY,
        confidence=GESTURE_CONFIDENCE,
        handedness=Handedness.RIGHT,
        timestamp=TIMESTAMP,
    )


def test_four_executions_rotate_through_three_urls_without_randomness() -> None:
    opener = RecordingLinkOpener()
    action = OpenLinksAction(urls=URLS, opener=opener)
    context = _context()

    for _ in range(4):
        action.execute(context)

    assert opener.urls == [URLS[0], URLS[1], URLS[2], URLS[0]]


def test_single_url_is_reopened_on_every_execution() -> None:
    opener = RecordingLinkOpener()
    action = OpenLinksAction(urls=("https://unico.example",), opener=opener)
    context = _context()

    action.execute(context)
    action.execute(context)

    assert opener.urls == ["https://unico.example", "https://unico.example"]


def test_empty_urls_raise_config_error() -> None:
    with pytest.raises(ConfigError, match="al menos una URL"):
        OpenLinksAction(urls=(), opener=RecordingLinkOpener())


class FailingOnceLinkOpener:
    """Fallo simulado en la primera apertura para fijar el avance del indice."""

    def __init__(self) -> None:
        self.urls: list[str] = []
        self.should_fail = True

    def open(self, url: str) -> None:
        if self.should_fail:
            msg = "fallo simulado"
            raise ActionError(msg)
        self.urls.append(url)


def test_index_does_not_advance_when_opener_fails() -> None:
    opener = FailingOnceLinkOpener()
    action = OpenLinksAction(urls=URLS, opener=opener)
    context = _context()

    with pytest.raises(ActionError, match="fallo simulado"):
        action.execute(context)

    opener.should_fail = False
    action.execute(context)

    assert opener.urls == [URLS[0]]
