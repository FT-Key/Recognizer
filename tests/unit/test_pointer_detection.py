"""Tests del processor que mueve el puntero con la punta del indice."""

from collections.abc import Callable

import numpy as np
import pytest
from numpy.typing import NDArray

from recognizer.core.domain.events import DomainEvent, PointerMoved
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.gesture import (
    GESTURE_POINTING_UP,
    GESTURE_VICTORY,
    GestureId,
    StableGesture,
)
from recognizer.core.domain.hand import (
    HAND_LANDMARK_COUNT,
    INDEX_FINGER_TIP_LANDMARK_INDEX,
    Handedness,
    HandLandmarks,
    Point,
)
from recognizer.core.domain.pointer import PointerCalibration, PointerPosition
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.pipeline.pointer_detection import PointerDetectionProcessor
from recognizer.core.pointer.smoothing import ExponentialSmoothing, PointerSmoothing
from recognizer.core.ports.event_bus import EventT

FRAME_TIMESTAMP = 2.0
FRAME_SHAPE = (4, 6, 3)
HAND_CONFIDENCE = 0.9
GESTURE_CONFIDENCE = 0.8
ZONE_MIN = 0.2
ZONE_MAX = 0.8
TIP_X = 0.35
TIP_Y = 0.35
CALIBRATED_X = 0.75
CALIBRATED_Y = 0.25
OTHER_X = 0.1
OTHER_Y = 0.0
DEFAULT_POINT = 0.5
SHORT_POINTS = 5
SMOOTHING_ALPHA = 0.5
FIRST_TIMESTAMP = 1.0
SECOND_TIMESTAMP = 2.0


class RecordingBus:
    """Doble de EventBus que acumula los eventos publicados."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    def subscribe(self, event_type: type[EventT], handler: Callable[[EventT], None]) -> None:
        del event_type, handler

    def publish(self, event: DomainEvent) -> None:
        self.events.append(event)


class SpySmoothing:
    """Doble de PointerSmoothing que cuenta reinicios y delega en un EMA interno."""

    def __init__(self) -> None:
        self.resets = 0
        self.targets: list[PointerPosition] = []
        self._inner: PointerSmoothing = ExponentialSmoothing(alpha=SMOOTHING_ALPHA)

    def reset(self) -> None:
        self.resets += 1
        self._inner.reset()

    def smooth(self, target: PointerPosition) -> PointerPosition:
        self.targets.append(target)
        return self._inner.smooth(target)


def _point(x: float, y: float) -> Point:
    return Point(x=x, y=y, z=0.0)


def _hand(
    *,
    handedness: Handedness = Handedness.RIGHT,
    points_count: int = HAND_LANDMARK_COUNT,
    tip: Point | None = None,
    other: Point | None = None,
) -> HandLandmarks:
    base = other or _point(DEFAULT_POINT, DEFAULT_POINT)
    points = [base] * points_count
    if tip is not None and points_count > INDEX_FINGER_TIP_LANDMARK_INDEX:
        points[INDEX_FINGER_TIP_LANDMARK_INDEX] = tip
    return HandLandmarks(
        handedness=handedness,
        confidence=HAND_CONFIDENCE,
        points=tuple(points),
    )


def _gesture(
    *,
    name: GestureId = GESTURE_POINTING_UP,
    handedness: Handedness = Handedness.RIGHT,
) -> StableGesture:
    return StableGesture(name=name, confidence=GESTURE_CONFIDENCE, handedness=handedness)


def _context(
    timestamp: float = FRAME_TIMESTAMP,
    *,
    hands: tuple[HandLandmarks, ...] = (),
    gestures: tuple[StableGesture, ...] = (),
    pointer: PointerPosition | None = None,
) -> FrameContext:
    data: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    return FrameContext(
        frame=Frame(data=data, timestamp=timestamp),
        hands=hands,
        gestures=gestures,
        pointer=pointer,
    )


def _processor(
    bus: RecordingBus,
    *,
    smoothing: PointerSmoothing | None = None,
    activation_gesture: GestureId = GESTURE_POINTING_UP,
) -> PointerDetectionProcessor:
    return PointerDetectionProcessor(
        bus=bus,
        calibration=PointerCalibration(
            x_min=ZONE_MIN,
            x_max=ZONE_MAX,
            y_min=ZONE_MIN,
            y_max=ZONE_MAX,
            mirror_x=True,
        ),
        smoothing=smoothing or SpySmoothing(),
        activation_gesture=activation_gesture,
    )


def _only_event(bus: RecordingBus) -> PointerMoved:
    assert len(bus.events) == 1
    event = bus.events[0]
    assert isinstance(event, PointerMoved)
    return event


def test_active_gesture_publishes_calibrated_position_and_sets_context() -> None:
    bus = RecordingBus()
    processor = _processor(bus)

    context = processor.process(
        _context(
            hands=(_hand(tip=_point(TIP_X, TIP_Y)),),
            gestures=(_gesture(),),
        )
    )

    event = _only_event(bus)
    assert event.timestamp == FRAME_TIMESTAMP
    assert event.x == pytest.approx(CALIBRATED_X)
    assert event.y == pytest.approx(CALIBRATED_Y)
    assert context.pointer is not None
    assert context.pointer.x == pytest.approx(CALIBRATED_X)
    assert context.pointer.y == pytest.approx(CALIBRATED_Y)


def test_uses_landmark_eight_and_ignores_other_points() -> None:
    bus = RecordingBus()
    processor = _processor(bus)

    processor.process(
        _context(
            hands=(_hand(tip=_point(TIP_X, TIP_Y), other=_point(OTHER_X, OTHER_Y)),),
            gestures=(_gesture(),),
        )
    )

    event = _only_event(bus)
    assert event.x == pytest.approx(CALIBRATED_X)
    assert event.y == pytest.approx(CALIBRATED_Y)


def test_without_gesture_resets_smoothing_and_clears_pointer() -> None:
    bus = RecordingBus()
    spy = SpySmoothing()
    processor = _processor(bus, smoothing=spy)

    context = processor.process(
        _context(
            hands=(_hand(tip=_point(TIP_X, TIP_Y)),),
            pointer=PointerPosition(x=DEFAULT_POINT, y=DEFAULT_POINT),
        )
    )

    assert bus.events == []
    assert context.pointer is None
    assert spy.resets == 1
    assert spy.targets == []


def test_without_matching_hand_resets_smoothing_and_clears_pointer() -> None:
    bus = RecordingBus()
    spy = SpySmoothing()
    processor = _processor(bus, smoothing=spy)

    context = processor.process(_context(gestures=(_gesture(),)))

    assert bus.events == []
    assert context.pointer is None
    assert spy.resets == 1
    assert spy.targets == []


def test_with_incomplete_points_resets_smoothing_and_clears_pointer() -> None:
    bus = RecordingBus()
    spy = SpySmoothing()
    processor = _processor(bus, smoothing=spy)

    context = processor.process(
        _context(
            hands=(_hand(points_count=SHORT_POINTS),),
            gestures=(_gesture(),),
        )
    )

    assert bus.events == []
    assert context.pointer is None
    assert spy.resets == 1
    assert spy.targets == []


def test_with_mismatched_handedness_resets_smoothing_and_clears_pointer() -> None:
    bus = RecordingBus()
    spy = SpySmoothing()
    processor = _processor(bus, smoothing=spy)

    context = processor.process(
        _context(
            hands=(_hand(handedness=Handedness.LEFT, tip=_point(TIP_X, TIP_Y)),),
            gestures=(_gesture(handedness=Handedness.RIGHT),),
        )
    )

    assert bus.events == []
    assert context.pointer is None
    assert spy.resets == 1
    assert spy.targets == []


def test_configured_activation_gesture_is_used() -> None:
    bus = RecordingBus()
    processor = _processor(bus, activation_gesture=GESTURE_VICTORY)

    context = processor.process(
        _context(
            hands=(_hand(tip=_point(TIP_X, TIP_Y)),),
            gestures=(_gesture(name=GESTURE_VICTORY),),
        )
    )

    event = _only_event(bus)
    assert event.x == pytest.approx(CALIBRATED_X)
    assert event.y == pytest.approx(CALIBRATED_Y)
    assert context.pointer is not None
    assert context.pointer.x == pytest.approx(CALIBRATED_X)


def test_smoothing_is_applied_between_frames() -> None:
    bus = RecordingBus()
    processor = _processor(bus, smoothing=ExponentialSmoothing(alpha=SMOOTHING_ALPHA))
    first_tip = _point(0.8, 0.2)
    second_tip = _point(0.2, 0.8)

    first = processor.process(
        _context(
            FIRST_TIMESTAMP,
            hands=(_hand(tip=first_tip),),
            gestures=(_gesture(),),
        )
    )
    second = processor.process(
        _context(
            SECOND_TIMESTAMP,
            hands=(_hand(tip=second_tip),),
            gestures=(_gesture(),),
        )
    )

    assert first.pointer == PointerPosition(x=0.0, y=0.0)
    assert second.pointer == PointerPosition(x=SMOOTHING_ALPHA, y=SMOOTHING_ALPHA)
    assert len(bus.events) == 2
    first_event = bus.events[0]
    second_event = bus.events[1]
    assert isinstance(first_event, PointerMoved)
    assert isinstance(second_event, PointerMoved)
    assert first_event.x == pytest.approx(0.0)
    assert second_event.x == pytest.approx(SMOOTHING_ALPHA)
    assert second_event.y == pytest.approx(SMOOTHING_ALPHA)


def test_two_hands_clear_pointer_even_with_activation_gesture_hand() -> None:
    bus = RecordingBus()
    spy = SpySmoothing()
    processor = _processor(bus, smoothing=spy)

    context = processor.process(
        _context(
            hands=(
                _hand(tip=_point(TIP_X, TIP_Y)),
                _hand(
                    handedness=Handedness.LEFT,
                    tip=_point(OTHER_X, OTHER_Y),
                ),
            ),
            gestures=(_gesture(),),
            pointer=PointerPosition(x=DEFAULT_POINT, y=DEFAULT_POINT),
        )
    )

    assert bus.events == []
    assert context.pointer is None
    assert spy.resets == 1
    assert spy.targets == []


def test_single_hand_still_publishes_pointer() -> None:
    bus = RecordingBus()
    processor = _processor(bus)

    context = processor.process(
        _context(
            hands=(_hand(tip=_point(TIP_X, TIP_Y)),),
            gestures=(_gesture(),),
        )
    )

    assert context.pointer is not None
    assert _only_event(bus).x == pytest.approx(CALIBRATED_X)
