"""Puerto de apertura de enlaces en el navegador configurado."""

from typing import Protocol


class LinkOpener(Protocol):
    """Abre una URL en el navegador configurado."""

    def open(self, url: str) -> None:
        """Abre una URL en el navegador configurado."""
        ...
