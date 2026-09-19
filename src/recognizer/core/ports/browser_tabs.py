"""Puerto de control de pestanas en el navegador Chromium."""

from collections.abc import Sequence
from typing import Protocol

from recognizer.core.domain.browser import TabKey


class BrowserTabs(Protocol):
    """Controla pestanas en una instancia Chromium via CDP."""

    def ensure(self, *, tab: TabKey, url: str) -> None:
        """Abre la URL en la pestana registrada (o la crea) y la enfoca."""
        ...

    def seek_media(self, *, tab: TabKey, fraction: float) -> None:
        """Posiciona el <video> de la pestana en fraction (0.0..1.0) de su duracion."""
        ...

    def press_keys(self, *, tab: TabKey, keys: Sequence[str]) -> None:
        """Envia teclas a la pestana (CDP Input.dispatchKeyEvent)."""
        ...
