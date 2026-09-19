"""Tests de las acciones que controlan pestanas del navegador."""

from collections.abc import Sequence

from recognizer.core.actions.browser import OpenTabAction, TabPressAction, TabSeekAction
from recognizer.core.domain.action import ActionContext
from recognizer.core.domain.browser import TabKey
from recognizer.core.domain.gesture import GESTURE_VICTORY
from recognizer.core.domain.hand import Handedness


class FakeBrowserTabs:
    """Doble de BrowserTabs que registra todas las llamadas."""

    def __init__(self) -> None:
        self.ensure_calls: list[tuple[TabKey, str]] = []
        self.seek_calls: list[tuple[TabKey, float]] = []
        self.press_calls: list[tuple[TabKey, tuple[str, ...]]] = []

    def ensure(self, *, tab: TabKey, url: str) -> None:
        self.ensure_calls.append((tab, url))

    def seek_media(self, *, tab: TabKey, fraction: float) -> None:
        self.seek_calls.append((tab, fraction))

    def press_keys(self, *, tab: TabKey, keys: Sequence[str]) -> None:
        self.press_calls.append((tab, tuple(keys)))


def _context() -> ActionContext:
    return ActionContext(
        gesture=GESTURE_VICTORY,
        confidence=0.85,
        handedness=Handedness.RIGHT,
        timestamp=3.5,
    )


class TestOpenTabAction:
    def test_first_call_uses_first_url(self) -> None:
        tabs = FakeBrowserTabs()
        action = OpenTabAction(
            urls=("https://a.example", "https://b.example"),
            browser=tabs,
            tab=TabKey("v"),
        )
        action.execute(_context())
        assert len(tabs.ensure_calls) == 1
        assert tabs.ensure_calls[0] == (TabKey("v"), "https://a.example")

    def test_rotates_through_urls(self) -> None:
        tabs = FakeBrowserTabs()
        urls = ("https://a.example", "https://b.example", "https://c.example")
        action = OpenTabAction(
            urls=urls,
            browser=tabs,
            tab=TabKey("v"),
        )
        ctx = _context()
        for _ in range(4):
            action.execute(ctx)

        assert tabs.ensure_calls == [
            (TabKey("v"), "https://a.example"),
            (TabKey("v"), "https://b.example"),
            (TabKey("v"), "https://c.example"),
            (TabKey("v"), "https://a.example"),
        ]

    def test_single_url_always_same(self) -> None:
        tabs = FakeBrowserTabs()
        action = OpenTabAction(
            urls=("https://unico.example",),
            browser=tabs,
            tab=TabKey("v"),
        )
        ctx = _context()
        action.execute(ctx)
        action.execute(ctx)
        assert tabs.ensure_calls == [
            (TabKey("v"), "https://unico.example"),
            (TabKey("v"), "https://unico.example"),
        ]


class TestTabSeekAction:
    def test_calls_seek_media(self) -> None:
        tabs = FakeBrowserTabs()
        action = TabSeekAction(
            tab=TabKey("v"),
            fraction=0.4,
            browser=tabs,
        )
        action.execute(_context())
        assert tabs.seek_calls == [(TabKey("v"), 0.4)]

    def test_seek_zero(self) -> None:
        tabs = FakeBrowserTabs()
        action = TabSeekAction(
            tab=TabKey("v"),
            fraction=0.0,
            browser=tabs,
        )
        action.execute(_context())
        assert tabs.seek_calls == [(TabKey("v"), 0.0)]

    def test_seek_one(self) -> None:
        tabs = FakeBrowserTabs()
        action = TabSeekAction(
            tab=TabKey("v"),
            fraction=1.0,
            browser=tabs,
        )
        action.execute(_context())
        assert tabs.seek_calls == [(TabKey("v"), 1.0)]


class TestTabPressAction:
    def test_calls_press_keys(self) -> None:
        tabs = FakeBrowserTabs()
        action = TabPressAction(
            tab=TabKey("v"),
            keys=("a", "b"),
            browser=tabs,
        )
        action.execute(_context())
        assert tabs.press_calls == [(TabKey("v"), ("a", "b"))]

    def test_single_key(self) -> None:
        tabs = FakeBrowserTabs()
        action = TabPressAction(
            tab=TabKey("v"),
            keys=("enter",),
            browser=tabs,
        )
        action.execute(_context())
        assert tabs.press_calls == [(TabKey("v"), ("enter",))]

    def test_empty_keys(self) -> None:
        tabs = FakeBrowserTabs()
        action = TabPressAction(
            tab=TabKey("v"),
            keys=(),
            browser=tabs,
        )
        action.execute(_context())
        assert tabs.press_calls == [(TabKey("v"), ())]
