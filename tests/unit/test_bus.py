"""Tests del bus de eventos in-process."""

from dataclasses import dataclass

from recognizer.core.bus import InProcessEventBus
from recognizer.core.domain.events import DomainEvent, HandsDetected

EVENT_TIMESTAMP = 1.5
OTHER_VALUE = 7


@dataclass(frozen=True, slots=True)
class OtherEvent(DomainEvent):
    """Evento distinto para comprobar el despacho por tipo exacto."""

    value: int


def _hands_event() -> HandsDetected:
    return HandsDetected(timestamp=EVENT_TIMESTAMP, hands=())


def test_handler_receives_event() -> None:
    bus = InProcessEventBus()
    received: list[HandsDetected] = []
    bus.subscribe(HandsDetected, received.append)

    event = _hands_event()
    bus.publish(event)

    assert received == [event]


def test_multiple_handlers_are_called() -> None:
    bus = InProcessEventBus()
    first: list[float] = []
    second: list[float] = []

    def first_handler(event: HandsDetected) -> None:
        first.append(event.timestamp)

    def second_handler(event: HandsDetected) -> None:
        second.append(event.timestamp)

    bus.subscribe(HandsDetected, first_handler)
    bus.subscribe(HandsDetected, second_handler)
    bus.publish(_hands_event())

    assert first == [EVENT_TIMESTAMP]
    assert second == [EVENT_TIMESTAMP]


def test_handler_for_other_event_type_is_not_called() -> None:
    bus = InProcessEventBus()
    received: list[OtherEvent] = []
    bus.subscribe(OtherEvent, received.append)

    bus.publish(_hands_event())

    assert received == []


def test_publish_without_subscribers_does_not_fail() -> None:
    InProcessEventBus().publish(_hands_event())


def test_same_handler_subscribed_twice_is_called_twice() -> None:
    bus = InProcessEventBus()
    calls: list[HandsDetected] = []
    bus.subscribe(HandsDetected, calls.append)
    bus.subscribe(HandsDetected, calls.append)

    event = _hands_event()
    bus.publish(event)

    assert calls == [event, event]


def test_other_event_handler_receives_its_own_event() -> None:
    bus = InProcessEventBus()
    received: list[OtherEvent] = []
    bus.subscribe(OtherEvent, received.append)

    event = OtherEvent(timestamp=EVENT_TIMESTAMP, value=OTHER_VALUE)
    bus.publish(event)

    assert received == [event]
