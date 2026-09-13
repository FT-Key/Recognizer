"""Tests de las acciones locales que delegan en los puertos."""

from collections.abc import Sequence

from recognizer.core.actions.local import CommandAction, HotkeyAction, MediaKeyAction
from recognizer.core.actions.noop import NoOpAction
from recognizer.core.domain.action import ActionContext, MediaKey
from recognizer.core.domain.gesture import GestureName
from recognizer.core.domain.hand import Handedness

GESTURE_CONFIDENCE = 0.9
TIMESTAMP = 1.0


class RecordingKeySender:
    """Doble de KeySender que registra las pulsaciones recibidas."""

    def __init__(self) -> None:
        self.media: list[MediaKey] = []
        self.hotkeys: list[tuple[str, ...]] = []

    def press_media(self, key: MediaKey) -> None:
        self.media.append(key)

    def hotkey(self, keys: Sequence[str]) -> None:
        self.hotkeys.append(tuple(keys))


class RecordingCommandRunner:
    """Doble de CommandRunner que registra los argv recibidos."""

    def __init__(self) -> None:
        self.commands: list[tuple[str, ...]] = []

    def run(self, argv: Sequence[str]) -> None:
        self.commands.append(tuple(argv))


def _context() -> ActionContext:
    return ActionContext(
        gesture=GestureName.VICTORY,
        confidence=GESTURE_CONFIDENCE,
        handedness=Handedness.RIGHT,
        timestamp=TIMESTAMP,
    )


def test_media_key_action_delegates_to_sender() -> None:
    sender = RecordingKeySender()
    action = MediaKeyAction(key=MediaKey.VOLUME_UP, sender=sender)

    action.execute(_context())

    assert sender.media == [MediaKey.VOLUME_UP]
    assert sender.hotkeys == []


def test_hotkey_action_delegates_to_sender() -> None:
    sender = RecordingKeySender()
    action = HotkeyAction(keys=["ctrl", "shift", "m"], sender=sender)

    action.execute(_context())

    assert sender.hotkeys == [("ctrl", "shift", "m")]
    assert sender.media == []


def test_command_action_delegates_to_runner() -> None:
    runner = RecordingCommandRunner()
    action = CommandAction(argv=["notepad.exe", "notas.txt"], runner=runner)

    action.execute(_context())

    assert runner.commands == [("notepad.exe", "notas.txt")]


def test_noop_action_does_nothing() -> None:
    action = NoOpAction()

    action.execute(_context())
