"""Alertas sonoras del sistema.

``SystemSoundAlert`` usa ``winsound`` (Windows) a traves de una fachada
inyectable, de modo que los tests no reproducen audio real. ``SilentAlert`` es
el Null Object para cuando la alerta sonora esta deshabilitada.
"""

import logging
from typing import Protocol

LOGGER = logging.getLogger("recognizer.alert")


class SoundFacade(Protocol):
    """Contrato de la fachada que aisla ``winsound``."""

    def message_beep(self) -> None:
        """Reproduce el sonido de alerta del sistema (no bloqueante)."""
        ...

    def stop(self) -> None:
        """Detiene cualquier sonido asincrono en curso."""
        ...


class WinsoundFacade:
    """Fachada real sobre ``winsound``; degrada a no-op fuera de Windows."""

    def message_beep(self) -> None:
        try:
            import winsound

            winsound.MessageBeep(winsound.MB_ICONHAND)
        except (ImportError, OSError, RuntimeError) as exc:
            LOGGER.warning("No se pudo reproducir la alerta sonora: %s", exc)

    def stop(self) -> None:
        try:
            import winsound

            winsound.PlaySound(None, winsound.SND_PURGE)
        except (ImportError, OSError, RuntimeError) as exc:
            LOGGER.warning("No se pudo detener la alerta sonora: %s", exc)


class SystemSoundAlert:
    """Alerta sonora del sistema; la fachada es inyectable para tests."""

    def __init__(self, facade: SoundFacade | None = None) -> None:
        self._facade = facade if facade is not None else WinsoundFacade()

    def notify(self) -> None:
        """Reproduce el sonido de alerta del sistema."""
        self._facade.message_beep()

    def close(self) -> None:
        """Detiene el sonido en curso; es idempotente."""
        self._facade.stop()

    def __enter__(self) -> "SystemSoundAlert":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


class SilentAlert:
    """Alerta nula: no hace nada (alerta sonora deshabilitada)."""

    def notify(self) -> None:
        """No-op."""

    def close(self) -> None:
        """No-op."""

    def __enter__(self) -> "SilentAlert":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None
