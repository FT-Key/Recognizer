"""Suavizado del puntero como Strategy (Null Object y media movil exponencial)."""

from typing import Protocol

from recognizer.core.domain.pointer import PointerPosition, SmoothingKind
from recognizer.core.errors import ConfigError


class PointerSmoothing(Protocol):
    """Suaviza las posiciones objetivo del puntero."""

    def reset(self) -> None:
        """Olvida el estado acumulado, por ejemplo al perder el gesto."""
        ...

    def smooth(self, target: PointerPosition) -> PointerPosition:
        """Devuelve la posicion suavizada hacia el objetivo."""
        ...


class NoSmoothing:
    """No suaviza: devuelve el objetivo tal cual (Null Object)."""

    def reset(self) -> None:
        """No hay estado que limpiar."""
        return

    def smooth(self, target: PointerPosition) -> PointerPosition:
        """Devuelve el objetivo sin cambios."""
        return target


class ExponentialSmoothing:
    """Media movil exponencial por eje."""

    def __init__(self, *, alpha: float) -> None:
        self._alpha = alpha
        self._previous: PointerPosition | None = None

    def reset(self) -> None:
        """Olvida la posicion previa."""
        self._previous = None

    def smooth(self, target: PointerPosition) -> PointerPosition:
        """Mezcla el objetivo con la posicion previa."""
        previous = self._previous
        if previous is None:
            self._previous = target
            return target
        complement = 1.0 - self._alpha
        position = PointerPosition(
            x=self._alpha * target.x + complement * previous.x,
            y=self._alpha * target.y + complement * previous.y,
        )
        self._previous = position
        return position


def create_smoothing(*, kind: SmoothingKind, alpha: float) -> PointerSmoothing:
    """Crea el suavizado configurado.

    Raises:
        ConfigError: si el tipo de suavizado no esta soportado.
    """
    match kind:
        case SmoothingKind.NONE:
            return NoSmoothing()
        case SmoothingKind.EMA:
            return ExponentialSmoothing(alpha=alpha)
    msg = f"Suavizado no soportado: {kind.value}"
    raise ConfigError(msg)
