"""Tests del processor de deteccion de manos y gestos."""

from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray

from recognizer.core.domain.events import DomainEvent, HandsDetected
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.gesture import DetectedGesture, GestureName, GestureRecognition
from recognizer.core.domain.hand import Handedness, HandLandmarks, Point
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.pipeline.gesture_detection import GestureDetectionProcessor
from recognizer.core.ports.event_bus import EventT

FRAME_TIMESTAMP = 2.0
HAND_CONFIDENCE = 0.9
GESTURE_CONFIDENCE = 0.8


class FakeClassifier:
    """Doble de GestureClassifier con una clasificacion predefinida."""

    def __init__(self, recognition: GestureRecognition) -> None:
        self.recognition = recognition
        self.classified_frames: list[Frame] = []

    def open(self) -> None:
        pass

    def classify(self, frame: Frame) -> GestureRecognition:
        self.classified_frames.append(frame)
        return self.recognition

    def close(self) -> None:
        pass


class RecordingBus:
    """Doble de EventBus que acumula los eventos publicados."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    def subscribe(self, event_type: type[EventT], handler: Callable[[EventT], None]) -> None:
        del event_type, handler

    def publish(self, event: DomainEvent) -> None:
        self.events.append(event)


def _frame() -> Frame:
    data: NDArray[np.uint8] = np.zeros((4, 6, 3), dtype=np.uint8)
    return Frame(data=data, timestamp=FRAME_TIMESTAMP)


def _hand() -> HandLandmarks:
    return HandLandmarks(
        handedness=Handedness.RIGHT,
        confidence=HAND_CONFIDENCE,
        points=(Point(x=0.5, y=0.5, z=0.0),),
    )


def _recognition() -> GestureRecognition:
    hand = _hand()
    detection = DetectedGesture(
        name=GestureName.VICTORY,
        confidence=GESTURE_CONFIDENCE,
        handedness=Handedness.RIGHT,
    )
    return GestureRecognition(hands=(hand,), detections=(detection,))


def test_process_classifies_publishes_and_updates_context() -> None:
    recognition = _recognition()
    classifier = FakeClassifier(recognition)
    bus = RecordingBus()
    processor = GestureDetectionProcessor(classifier=classifier, bus=bus)
    frame = _frame()

    context = processor.process(FrameContext(frame=frame))

    assert context.frame is frame
    assert context.hands == recognition.hands
    assert context.detections == recognition.detections
    assert classifier.classified_frames == [frame]
    assert bus.events == [HandsDetected(timestamp=FRAME_TIMESTAMP, hands=recognition.hands)]


def test_process_with_empty_recognition_publishes_empty_hands() -> None:
    recognition = GestureRecognition(hands=(), detections=())
    classifier = FakeClassifier(recognition)
    bus = RecordingBus()
    processor = GestureDetectionProcessor(classifier=classifier, bus=bus)

    context = processor.process(FrameContext(frame=_frame()))

    assert context.hands == ()
    assert context.detections == ()
    assert bus.events == [HandsDetected(timestamp=FRAME_TIMESTAMP, hands=())]
