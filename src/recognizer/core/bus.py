"""Bus de eventos in-process."""

from collections.abc import Callable
from typing import cast

from recognizer.core.domain.events import DomainEvent
from recognizer.core.ports.event_bus import EventBus, EventT

Handler = Callable[[DomainEvent], None]


class InProcessEventBus(EventBus):
    """Bus sincrono que despacha a los handlers del tipo exacto del evento."""

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[Handler]] = {}

    def subscribe(self, event_type: type[EventT], handler: Callable[[EventT], None]) -> None:
        """Registra un handler para el tipo de evento indicado."""
        # Callable es invariante en su parametro: el cast documenta la conversion
        # del handler tipado al almacenamiento homogeneo del registro.
        self._handlers.setdefault(event_type, []).append(cast("Handler", handler))

    def publish(self, event: DomainEvent) -> None:
        """Entrega el evento a los handlers suscritos a su tipo exacto."""
        for handler in self._handlers.get(type(event), []):
            handler(event)
