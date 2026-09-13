"""Puerto del bus de eventos tipado in-process."""

from collections.abc import Callable
from typing import Protocol, TypeVar

from recognizer.core.domain.events import DomainEvent

EventT = TypeVar("EventT", bound=DomainEvent)


class EventBus(Protocol):
    """Publica eventos del dominio a suscriptores tipados."""

    def subscribe(self, event_type: type[EventT], handler: Callable[[EventT], None]) -> None:
        """Registra un handler para el tipo de evento indicado."""
        ...

    def publish(self, event: DomainEvent) -> None:
        """Entrega el evento a los handlers suscritos a su tipo exacto."""
        ...
