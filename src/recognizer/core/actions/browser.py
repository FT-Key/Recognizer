"""Acciones que controlan pestanas del navegador via CDP."""

from collections.abc import Sequence

from recognizer.core.domain.action import Action, ActionContext
from recognizer.core.domain.browser import TabKey
from recognizer.core.ports.browser_tabs import BrowserTabs


class OpenTabAction(Action):
    """Abre o enfoca una pestana registrada en el navegador controlado.

    La lista de URLs se recorre de forma rotatoria: cada ejecucion abre la URL
    actual y avanza al siguiente indice.
    """

    def __init__(
        self,
        *,
        urls: Sequence[str],
        browser: BrowserTabs,
        tab: TabKey,
    ) -> None:
        self._urls = tuple(urls)
        self._browser = browser
        self._tab = tab
        self._index = 0

    def execute(self, context: ActionContext) -> None:
        """Abre la URL actual y avanza el indice rotatorio."""
        del context
        self._browser.ensure(tab=self._tab, url=self._urls[self._index])
        self._index = (self._index + 1) % len(self._urls)


class TabSeekAction(Action):
    """Posiciona el video de una pestana en una fraccion de su duracion."""

    def __init__(
        self,
        *,
        tab: TabKey,
        fraction: float,
        browser: BrowserTabs,
    ) -> None:
        self._tab = tab
        self._fraction = fraction
        self._browser = browser

    def execute(self, context: ActionContext) -> None:
        """Delega el seek al navegador."""
        del context
        self._browser.seek_media(tab=self._tab, fraction=self._fraction)


class TabPressAction(Action):
    """Envia teclas a una pestana del navegador controlado."""

    def __init__(
        self,
        *,
        tab: TabKey,
        keys: Sequence[str],
        browser: BrowserTabs,
    ) -> None:
        self._tab = tab
        self._keys = tuple(keys)
        self._browser = browser

    def execute(self, context: ActionContext) -> None:
        """Delega las teclas al navegador."""
        del context
        self._browser.press_keys(tab=self._tab, keys=self._keys)
