"""Acciones locales que delegan en los puertos de teclado y comandos."""

from collections.abc import Sequence

from recognizer.core.domain.action import Action, ActionContext, MediaKey
from recognizer.core.ports.command_runner import CommandRunner
from recognizer.core.ports.key_sender import KeySender


class MediaKeyAction(Action):
    """Pulsa una tecla multimedia ante un gesto confirmado."""

    def __init__(self, *, key: MediaKey, sender: KeySender) -> None:
        self._key = key
        self._sender = sender

    def execute(self, context: ActionContext) -> None:
        """Delega la pulsacion en el KeySender."""
        del context
        self._sender.press_media(self._key)


class HotkeyAction(Action):
    """Pulsa una combinacion de teclas ante un gesto confirmado."""

    def __init__(self, *, keys: Sequence[str], sender: KeySender) -> None:
        self._keys = tuple(keys)
        self._sender = sender

    def execute(self, context: ActionContext) -> None:
        """Delega la combinacion en el KeySender."""
        del context
        self._sender.hotkey(self._keys)


class CommandAction(Action):
    """Ejecuta un comando local ante un gesto confirmado."""

    def __init__(self, *, argv: Sequence[str], runner: CommandRunner) -> None:
        self._argv = tuple(argv)
        self._runner = runner

    def execute(self, context: ActionContext) -> None:
        """Delega el argv en el CommandRunner."""
        del context
        self._runner.run(self._argv)
