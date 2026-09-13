"""Tests del pipeline, el builder y el processor de deteccion de manos."""

from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray

from recognizer.core.domain.events import DomainEvent, HandsDetected
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.hand import Handedness, HandLandmarks, Point
from recognizer.core.pipeline.builder import Pipeline, PipelineBuilder
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.pipeline.hand_detection import HandDetectionProcessor
from recognizer.core.ports.event_bus import EventT

FRAME_TIMESTAMP = 2.0
HAND_CONFIDENCE = 0.9


class RecordingProcessor:
    """Processor que registra su nombre al ejecutarse."""

    def __init__(self, *, name: str, log: list[str]) -> None:
        self._name = name
        self._log = log

    def process(self, context: FrameContext) -> FrameContext:
        self._log.append(self._name)
        return context


class FakeTracker:
    """Doble de HandTracker con manos predefinidas."""

    def __init__(self, hands: tuple[HandLandmarks, ...] = ()) -> None:
        self.hands = hands
        self.detected_frames: list[Frame] = []

    def open(self) -> None:
        pass

    def detect(self, frame: Frame) -> tuple[HandLandmarks, ...]:
        self.detected_frames.append(frame)
        return self.hands

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


def test_processors_run_in_order() -> None:
    log: list[str] = []
    pipeline = (
        PipelineBuilder()
        .add(RecordingProcessor(name="first", log=log))
        .add(RecordingProcessor(name="second", log=log))
        .build()
    )

    pipeline.run(_frame())

    assert log == ["first", "second"]


def test_add_returns_same_builder() -> None:
    builder = PipelineBuilder()
    log: list[str] = []
    assert builder.add(RecordingProcessor(name="only", log=log)) is builder


def test_empty_pipeline_returns_context_with_frame_and_no_hands() -> None:
    frame = _frame()

    context = Pipeline(processors=()).run(frame)

    assert context.frame is frame
    assert context.hands == ()


def test_hand_detection_processor_publishes_and_updates_context() -> None:
    hands = (_hand(),)
    tracker = FakeTracker(hands=hands)
    bus = RecordingBus()
    processor = HandDetectionProcessor(tracker=tracker, bus=bus)
    frame = _frame()

    context = processor.process(FrameContext(frame=frame))

    assert context.frame is frame
    assert context.hands == hands
    assert tracker.detected_frames == [frame]
    assert bus.events == [HandsDetected(timestamp=FRAME_TIMESTAMP, hands=hands)]


def test_hand_detection_processor_publishes_empty_hands() -> None:
    tracker = FakeTracker(hands=())
    bus = RecordingBus()
    processor = HandDetectionProcessor(tracker=tracker, bus=bus)

    processor.process(FrameContext(frame=_frame()))

    assert bus.events == [HandsDetected(timestamp=FRAME_TIMESTAMP, hands=())]
