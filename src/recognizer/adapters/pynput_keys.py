"""Adaptador de teclado basado en pynput."""

from collections.abc import Sequence
from typing import Protocol, cast

from pynput.keyboard import Controller, Key

from recognizer.core.domain.action import MediaKey
from recognizer.core.errors import ActionError
from recognizer.core.ports.key_sender import KeySender

MEDIA_KEY_BY_NAME: dict[MediaKey, Key] = {
    MediaKey.VOLUME_UP: Key.media_volume_up,
    MediaKey.VOLUME_DOWN: Key.media_volume_down,
    MediaKey.VOLUME_MUTE: Key.media_volume_mute,
    MediaKey.PLAY_PAUSE: Key.media_play_pause,
    MediaKey.NEXT_TRACK: Key.media_next,
    MediaKey.PREVIOUS_TRACK: Key.media_previous,
}


class KeyController(Protocol):
    """Subconjunto de pynput.keyboard.Controller que usamos (permite dobles)."""

    def press(self, key: object) -> None:
        """Presiona una tecla."""
        ...

    def release(self, key: object) -> None:
        """Libera una tecla."""
        ...


class PynputKeySender(KeySender):
    """Envia teclas multimedia y combinaciones con pynput."""

    def __init__(self, *, controller: KeyController | None = None) -> None:
        # pynput no expone stubs: el cast fija la frontera tipada con la libreria.
        self._controller = controller or cast("KeyController", Controller())

    def press_media(self, key: MediaKey) -> None:
        """Pulsa y libera una tecla multimedia.

        Raises:
            ActionError: si la tecla no tiene mapeo o pynput falla.
        """
        resolved = MEDIA_KEY_BY_NAME.get(key)
        if resolved is None:
            msg = f"Tecla multimedia desconocida: {key.value}"
            raise ActionError(msg)
        try:
            self._controller.press(resolved)
            self._controller.release(resolved)
        except (OSError, ValueError) as exc:
            msg = f"No se pudo enviar la tecla multimedia: {key.value}"
            raise ActionError(msg) from exc

    def hotkey(self, keys: Sequence[str]) -> None:
        """Pulsa la combinacion en orden y la libera al reves.

        Raises:
            ActionError: si una tecla es desconocida o pynput falla.
        """
        resolved = [self._resolve_token(token) for token in keys]
        pressed: list[object] = []
        try:
            for token in resolved:
                self._controller.press(token)
                pressed.append(token)
        except (OSError, ValueError) as exc:
            msg = "No se pudo enviar la combinacion de teclas."
            raise ActionError(msg) from exc
        finally:
            for token in reversed(pressed):
                self._controller.release(token)

    def _resolve_token(self, token: str) -> object:
        if len(token) == 1:
            return token
        resolved: object | None = getattr(Key, token, None)
        if resolved is None:
            msg = f"Tecla desconocida: {token}"
            raise ActionError(msg)
        return resolved
