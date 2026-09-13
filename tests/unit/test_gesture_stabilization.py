"""Tests del estabilizador de gestos por lateralidad."""

from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray

from recognizer.core.domain.events import DomainEvent, GestureDetected, GestureReleased
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.gesture import DetectedGesture, GestureName, StableGesture
from recognizer.core.domain.hand import Handedness
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.pipeline.gesture_stabilization import GestureStabilizerProcessor
from recognizer.core.ports.event_bus import EventT

STABILIZATION_FRAMES = 3
RELEASE_FRAMES = 2
MIN_GESTURE_CONFIDENCE = 0.5
GESTURE_CONFIDENCE = 0.9
LOW_CONFIDENCE = 0.4
FRAME_SHAPE = (4, 6, 3)


class RecordingBus:
    """Doble de EventBus que acumula los eventos publicados."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    def subscribe(self, event_type: type[EventT], handler: Callable[[EventT], None]) -> None:
        del event_type, handler

    def publish(self, event: DomainEvent) -> None:
        self.events.append(event)


def _detection(
    name: GestureName = GestureName.VICTORY,
    *,
    confidence: float = GESTURE_CONFIDENCE,
    handedness: Handedness = Handedness.RIGHT,
) -> DetectedGesture:
    return DetectedGesture(name=name, confidence=confidence, handedness=handedness)


def _context(
    timestamp: float,
    detections: tuple[DetectedGesture, ...] = (),
) -> FrameContext:
    data: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    return FrameContext(frame=Frame(data=data, timestamp=timestamp), detections=detections)


def _processor(
    bus: RecordingBus,
    *,
    stabilization_frames: int = STABILIZATION_FRAMES,
    release_frames: int = RELEASE_FRAMES,
) -> GestureStabilizerProcessor:
    return GestureStabilizerProcessor(
        bus=bus,
        stabilization_frames=stabilization_frames,
        release_frames=release_frames,
        min_gesture_confidence=MIN_GESTURE_CONFIDENCE,
    )


def _confirmed(
    timestamp: float,
    gesture: GestureName = GestureName.VICTORY,
    *,
    confidence: float = GESTURE_CONFIDENCE,
    handedness: Handedness = Handedness.RIGHT,
) -> GestureDetected:
    return GestureDetected(
        timestamp=timestamp,
        gesture=gesture,
        confidence=confidence,
        handedness=handedness,
    )


def _released(
    timestamp: float,
    gesture: GestureName = GestureName.VICTORY,
    *,
    handedness: Handedness = Handedness.RIGHT,
) -> GestureReleased:
    return GestureReleased(timestamp=timestamp, gesture=gesture, handedness=handedness)


def test_confirm_after_n_consecutive_frames() -> None:
    bus = RecordingBus()
    processor = _processor(bus)

    processor.process(_context(0.1, (_detection(),)))
    processor.process(_context(0.2, (_detection(),)))
    assert bus.events == []

    context = processor.process(_context(0.3, (_detection(),)))

    assert bus.events == [_confirmed(0.3)]
    assert context.gestures == (
        StableGesture(
            name=GestureName.VICTORY,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.RIGHT,
        ),
    )


def test_confirmed_gesture_is_not_republished() -> None:
    bus = RecordingBus()
    processor = _processor(bus)
    for timestamp in (0.1, 0.2, 0.3):
        processor.process(_context(timestamp, (_detection(),)))
    assert bus.events == [_confirmed(0.3)]

    context = processor.process(_context(0.4, (_detection(confidence=0.8),)))

    assert bus.events == [_confirmed(0.3)]
    assert context.gestures == (
        StableGesture(
            name=GestureName.VICTORY,
            confidence=0.8,
            handedness=Handedness.RIGHT,
        ),
    )


def test_change_publishes_release_then_detection_in_order() -> None:
    bus = RecordingBus()
    processor = _processor(bus, release_frames=STABILIZATION_FRAMES)
    for timestamp in (0.1, 0.2, 0.3):
        processor.process(_context(timestamp, (_detection(),)))

    processor.process(_context(0.4, (_detection(GestureName.OPEN_PALM),)))
    processor.process(_context(0.5, (_detection(GestureName.OPEN_PALM),)))
    assert bus.events == [_confirmed(0.3)]

    context = processor.process(_context(0.6, (_detection(GestureName.OPEN_PALM),)))

    assert bus.events == [
        _confirmed(0.3),
        _released(0.6),
        _confirmed(0.6, GestureName.OPEN_PALM),
    ]
    assert context.gestures == (
        StableGesture(
            name=GestureName.OPEN_PALM,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.RIGHT,
        ),
    )


def test_release_after_m_missing_frames_and_no_repeat() -> None:
    bus = RecordingBus()
    processor = _processor(bus)
    for timestamp in (0.1, 0.2, 0.3):
        processor.process(_context(timestamp, (_detection(),)))

    processor.process(_context(0.4))
    assert bus.events == [_confirmed(0.3)]

    context = processor.process(_context(0.5))

    assert bus.events == [_confirmed(0.3), _released(0.5)]
    assert context.gestures == ()

    processor.process(_context(0.6))
    assert bus.events == [_confirmed(0.3), _released(0.5)]


def test_observing_confirmed_gesture_resets_missing_count() -> None:
    bus = RecordingBus()
    processor = _processor(bus)
    for timestamp in (0.1, 0.2, 0.3):
        processor.process(_context(timestamp, (_detection(),)))

    processor.process(_context(0.4))
    processor.process(_context(0.5, (_detection(),)))
    processor.process(_context(0.6))
    assert bus.events == [_confirmed(0.3)]

    processor.process(_context(0.7))
    assert bus.events == [_confirmed(0.3), _released(0.7)]


def test_ignored_detections_do_not_confirm_and_count_as_absence() -> None:
    bus = RecordingBus()
    processor = _processor(bus)
    ignored = (
        _detection(GestureName.NONE),
        _detection(confidence=LOW_CONFIDENCE),
        _detection(handedness=Handedness.UNKNOWN),
    )

    for timestamp in (0.1, 0.2, 0.3):
        context = processor.process(_context(timestamp, ignored))

    assert bus.events == []
    assert context.gestures == ()

    for timestamp in (1.1, 1.2, 1.3):
        processor.process(_context(timestamp, (_detection(),)))
    assert bus.events == [_confirmed(1.3)]

    processor.process(_context(1.4, ignored))
    processor.process(_context(1.5, ignored))

    assert bus.events == [_confirmed(1.3), _released(1.5)]


def test_single_stabilization_frame_confirms_immediately() -> None:
    bus = RecordingBus()
    processor = _processor(bus, stabilization_frames=1)

    context = processor.process(_context(0.1, (_detection(),)))

    assert bus.events == [_confirmed(0.1)]
    assert context.gestures == (
        StableGesture(
            name=GestureName.VICTORY,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.RIGHT,
        ),
    )


def test_two_hands_stabilize_independently() -> None:
    bus = RecordingBus()
    processor = _processor(bus)
    left_victory = _detection(GestureName.VICTORY, handedness=Handedness.LEFT)
    right_open_palm = _detection(GestureName.OPEN_PALM, handedness=Handedness.RIGHT)

    processor.process(_context(0.1, (left_victory, right_open_palm)))
    processor.process(_context(0.2, (left_victory, right_open_palm)))
    assert bus.events == []

    context = processor.process(_context(0.3, (left_victory, right_open_palm)))

    assert bus.events == [
        _confirmed(0.3, GestureName.VICTORY, handedness=Handedness.LEFT),
        _confirmed(0.3, GestureName.OPEN_PALM, handedness=Handedness.RIGHT),
    ]
    assert context.gestures == (
        StableGesture(
            name=GestureName.VICTORY,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.LEFT,
        ),
        StableGesture(
            name=GestureName.OPEN_PALM,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.RIGHT,
        ),
    )

    processor.process(_context(0.4, (right_open_palm,)))
    context = processor.process(_context(0.5, (right_open_palm,)))

    assert bus.events[-1] == _released(0.5, GestureName.VICTORY, handedness=Handedness.LEFT)
    assert context.gestures == (
        StableGesture(
            name=GestureName.OPEN_PALM,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.RIGHT,
        ),
    )


def test_release_before_stabilization_keeps_candidate_counting() -> None:
    bus = RecordingBus()
    processor = _processor(bus)
    for timestamp in (0.1, 0.2, 0.3):
        processor.process(_context(timestamp, (_detection(),)))
    assert bus.events == [_confirmed(0.3)]

    processor.process(_context(0.4, (_detection(GestureName.OPEN_PALM),)))
    assert bus.events == [_confirmed(0.3)]

    context = processor.process(_context(0.5, (_detection(GestureName.OPEN_PALM),)))

    assert bus.events == [_confirmed(0.3), _released(0.5)]
    assert context.gestures == ()

    context = processor.process(_context(0.6, (_detection(GestureName.OPEN_PALM),)))

    assert bus.events == [
        _confirmed(0.3),
        _released(0.5),
        _confirmed(0.6, GestureName.OPEN_PALM),
    ]
    assert context.gestures == (
        StableGesture(
            name=GestureName.OPEN_PALM,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.RIGHT,
        ),
    )


def test_reverted_candidate_restarts_without_events() -> None:
    bus = RecordingBus()
    processor = _processor(bus, stabilization_frames=2)
    processor.process(_context(0.1, (_detection(),)))
    processor.process(_context(0.2, (_detection(),)))
    assert bus.events == [_confirmed(0.2)]

    processor.process(_context(0.3, (_detection(GestureName.OPEN_PALM),)))
    processor.process(_context(0.4, (_detection(),)))

    assert bus.events == [_confirmed(0.2)]

    processor.process(_context(0.5, (_detection(GestureName.OPEN_PALM),)))
    processor.process(_context(0.6, (_detection(GestureName.OPEN_PALM),)))

    assert bus.events == [
        _confirmed(0.2),
        _released(0.6),
        _confirmed(0.6, GestureName.OPEN_PALM),
    ]


def test_highest_confidence_same_gesture_wins() -> None:
    bus = RecordingBus()
    processor = _processor(bus, stabilization_frames=1)

    context = processor.process(
        _context(
            0.1,
            (
                _detection(GestureName.VICTORY, confidence=0.6),
                _detection(GestureName.VICTORY, confidence=GESTURE_CONFIDENCE),
            ),
        )
    )

    assert bus.events == [_confirmed(0.1, confidence=GESTURE_CONFIDENCE)]
    assert context.gestures == (
        StableGesture(
            name=GestureName.VICTORY,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.RIGHT,
        ),
    )


def test_highest_confidence_gesture_wins_regardless_of_order() -> None:
    bus = RecordingBus()
    processor = _processor(bus, stabilization_frames=1)

    processor.process(
        _context(
            0.1,
            (
                _detection(GestureName.VICTORY, confidence=0.6),
                _detection(GestureName.OPEN_PALM, confidence=GESTURE_CONFIDENCE),
            ),
        )
    )

    assert bus.events == [_confirmed(0.1, GestureName.OPEN_PALM)]
