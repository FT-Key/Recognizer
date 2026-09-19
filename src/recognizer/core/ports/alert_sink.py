"""Puerto de alertas perceptibles (sonido, notificacion...)."""

from typing import Protocol


class AlertSink(Protocol):
    """Emite y detiene una alerta perceptible para el usuario."""

    def notify(self) -> None:
        """Dispara una alerta perceptible; no bloquea el bucle de camara."""
        ...

    def close(self) -> None:
        """Detiene la alerta y libera recursos; es idempotente."""
        ...
