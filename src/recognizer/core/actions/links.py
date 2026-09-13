"""Accion que abre enlaces de forma secuencial y rotatoria."""

from collections.abc import Sequence

from recognizer.core.domain.action import Action, ActionContext
from recognizer.core.errors import ConfigError
from recognizer.core.ports.link_opener import LinkOpener


class OpenLinksAction(Action):
    """Abre el siguiente enlace de una lista ante cada gesto confirmado.

    El indice vive en memoria y avanza de forma rotatoria, sin aleatoriedad:
    agotada la lista se vuelve al primer enlace.
    """

    def __init__(self, *, urls: Sequence[str], opener: LinkOpener) -> None:
        if not urls:
            msg = "OpenLinksAction requiere al menos una URL."
            raise ConfigError(msg)
        self._urls = tuple(urls)
        self._opener = opener
        self._index = 0

    def execute(self, context: ActionContext) -> None:
        """Abre el enlace actual y avanza el indice de forma rotatoria."""
        del context
        self._opener.open(self._urls[self._index])
        self._index = (self._index + 1) % len(self._urls)
