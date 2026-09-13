"""Puerto de envio de teclas al sistema."""

from collections.abc import Sequence
from typing import Protocol

from recognizer.core.domain.action import MediaKey


class KeySender(Protocol):
    """Envia teclas multimedia y combinaciones al sistema anfitrion."""

    def press_media(self, key: MediaKey) -> None:
        """Pulsa (y libera) una tecla multimedia."""
        ...

    def hotkey(self, keys: Sequence[str]) -> None:
        """Pulsa una combinacion de teclas y la libera al reves."""
        ...
