"""Processor que clasifica manos y gestos y publica el evento de manos."""

from dataclasses import replace

from recognizer.core.domain.events import HandsDetected
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.pipeline.processor import Processor
from recognizer.core.ports.event_bus import EventBus
from recognizer.core.ports.gesture_classifier import GestureClassifier


class GestureDetectionProcessor(Processor):
    """Clasifica manos y gestos, publica HandsDetected y anota el contexto."""

    def __init__(self, *, classifier: GestureClassifier, bus: EventBus) -> None:
        self._classifier = classifier
        self._bus = bus

    def process(self, context: FrameContext) -> FrameContext:
        """Clasifica el fotograma y publica las manos detectadas."""
        recognition = self._classifier.classify(context.frame)
        self._bus.publish(HandsDetected(timestamp=context.frame.timestamp, hands=recognition.hands))
        return replace(
            context,
            hands=recognition.hands,
            detections=recognition.detections,
        )
