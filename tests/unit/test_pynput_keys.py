"""Tests del adaptador de teclado pynput con un controlador falso."""

from collections.abc import Sequence
from typing import cast

import pytest
from pynput.keyboard import Key

from recognizer.adapters.pynput_keys import PynputKeySender
from recognizer.core.domain.action import MediaKey
from recognizer.core.domain.gesture import GESTURE_VICTORY
from recognizer.core.errors import ActionError

EXPECTED_MEDIA_KEYS: tuple[tuple[MediaKey, Key], ...] = (
    (MediaKey.VOLUME_UP, Key.media_volume_up),
    (MediaKey.VOLUME_DOWN, Key.media_volume_down),
    (MediaKey.VOLUME_MUTE, Key.media_volume_mute),
    (MediaKey.PLAY_PAUSE, Key.media_play_pause),
    (MediaKey.NEXT_TRACK, Key.media_next),
    (MediaKey.PREVIOUS_TRACK, Key.media_previous),
)

HOTKEY_TOKENS = ("ctrl", "shift", "m")
FAILING_PRESS_INDEX = 2


class RecordingKeyController:
    """Doble de KeyController que registra press y release en orden."""

    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []

    def press(self, key: object) -> None:
        self.events.append(("press", key))

    def release(self, key: object) -> None:
        self.events.append(("release", key))


class FailingKeyController:
    """Doble que falla en el press numero indicado."""

    def __init__(self, *, fail_on_press: int) -> None:
        self._fail_on_press = fail_on_press
        self._press_count = 0
        self.pressed: list[object] = []
        self.released: list[object] = []

    def press(self, key: object) -> None:
        self._press_count += 1
        if self._press_count == self._fail_on_press:
            msg = "sin teclado"
            raise OSError(msg)
        self.pressed.append(key)

    def release(self, key: object) -> None:
        self.released.append(key)


def test_hotkey_presses_in_order_and_releases_reversed() -> None:
    controller = RecordingKeyController()
    sender = PynputKeySender(controller=controller)

    sender.hotkey(HOTKEY_TOKENS)

    assert controller.events == [
        ("press", Key.ctrl),
        ("press", Key.shift),
        ("press", "m"),
        ("release", "m"),
        ("release", Key.shift),
        ("release", Key.ctrl),
    ]


def test_hotkey_rejects_unknown_token_without_pressing() -> None:
    controller = RecordingKeyController()
    sender = PynputKeySender(controller=controller)

    with pytest.raises(ActionError, match="desconocida"):
        sender.hotkey(["ctrl", "tecla-rara", "m"])

    assert controller.events == []


def test_hotkey_releases_pressed_keys_when_press_fails() -> None:
    controller = FailingKeyController(fail_on_press=FAILING_PRESS_INDEX)
    sender = PynputKeySender(controller=controller)

    with pytest.raises(ActionError, match="combinacion"):
        sender.hotkey(HOTKEY_TOKENS)

    assert controller.pressed == [Key.ctrl]
    assert controller.released == [Key.ctrl]


@pytest.mark.parametrize(("media_key", "expected"), EXPECTED_MEDIA_KEYS)
def test_press_media_maps_to_expected_key(media_key: MediaKey, expected: Key) -> None:
    controller = RecordingKeyController()
    sender = PynputKeySender(controller=controller)

    sender.press_media(media_key)

    assert controller.events == [("press", expected), ("release", expected)]


def test_press_media_rejects_unknown_key() -> None:
    controller = RecordingKeyController()
    sender = PynputKeySender(controller=controller)
    # cast documentado: simula una clave corrupta de otro enum StrEnum.
    unknown = cast(MediaKey, GESTURE_VICTORY)

    with pytest.raises(ActionError, match="desconocida"):
        sender.press_media(unknown)

    assert controller.events == []


def test_press_media_os_error_becomes_action_error() -> None:
    controller = FailingKeyController(fail_on_press=1)
    sender = PynputKeySender(controller=controller)

    with pytest.raises(ActionError, match="multimedia"):
        sender.press_media(MediaKey.VOLUME_UP)

    assert controller.pressed == []


def test_hotkey_accepts_any_sequence_typed_input() -> None:
    controller = RecordingKeyController()
    sender = PynputKeySender(controller=controller)
    keys: Sequence[str] = ["a", "b"]

    sender.hotkey(keys)

    assert controller.events == [
        ("press", "a"),
        ("press", "b"),
        ("release", "b"),
        ("release", "a"),
    ]
