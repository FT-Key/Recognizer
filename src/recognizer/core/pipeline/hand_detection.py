"""Processor que detecta manos y publica el evento del dominio."""

from dataclasses import replace

from recognizer.core.domain.events import HandsDetected
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.pipeline.processor import Processor
from recognizer.core.ports.event_bus import EventBus
from recognizer.core.ports.hand_tracker import HandTracker


class HandDetectionProcessor(Processor):
    """Detecta manos, publica HandsDetected y anota el contexto."""

    def __init__(self, *, tracker: HandTracker, bus: EventBus) -> None:
        self._tracker = tracker
        self._bus = bus

    def process(self, context: FrameContext) -> FrameContext:
        """Detecta manos en el fotograma y publica el evento siempre."""
        hands = self._tracker.detect(context.frame)
        self._bus.publish(HandsDetected(timestamp=context.frame.timestamp, hands=hands))
        return replace(context, hands=hands)
