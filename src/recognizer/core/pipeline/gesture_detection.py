"""Processor que clasifica manos y gestos y publica el evento de manos."""

import logging
from dataclasses import replace

from recognizer.core.domain.events import HandsDetected
from recognizer.core.errors import GestureClassifierError
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.pipeline.processor import Processor
from recognizer.core.ports.event_bus import EventBus
from recognizer.core.ports.gesture_classifier import GestureClassifier

logger = logging.getLogger("recognizer.gesture_detection")


class GestureDetectionProcessor(Processor):
    """Clasifica manos y gestos, publica HandsDetected y anota el contexto."""

    def __init__(self, *, classifier: GestureClassifier, bus: EventBus) -> None:
        self._classifier = classifier
        self._bus = bus

    def process(self, context: FrameContext) -> FrameContext:
        """Clasifica el fotograma y publica las manos detectadas."""
        try:
            recognition = self._classifier.classify(context.frame)
        except GestureClassifierError:
            logger.warning(
                "Fallo la clasificacion en este frame, se salta. "
                "Bug conocido de MediaPipe con ciertas posiciones de manos."
            )
            return context
        self._bus.publish(HandsDetected(timestamp=context.frame.timestamp, hands=recognition.hands))
        return replace(
            context,
            hands=recognition.hands,
            detections=recognition.detections,
        )
