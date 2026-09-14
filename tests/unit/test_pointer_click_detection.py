"""Tests del processor que detecta el pulgar abierto para click del puntero."""

from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray

from recognizer.core.domain.events import (
    DomainEvent,
    PointerClicked,
    PointerReleased,
)
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.gesture import (
    GESTURE_POINTING_UP,
    GESTURE_VICTORY,
    GestureId,
    StableGesture,
)
from recognizer.core.domain.hand import (
    HAND_LANDMARK_COUNT,
    INDEX_FINGER_MCP_LANDMARK_INDEX,
    MIDDLE_FINGER_MCP_LANDMARK_INDEX,
    THUMB_TIP_LANDMARK_INDEX,
    WRIST_LANDMARK_INDEX,
    Handedness,
    HandLandmarks,
    Point,
)
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.pipeline.pointer_click_detection import (
    PointerClickDetectionProcessor,
)
from recognizer.core.ports.event_bus import EventT

FRAME_TIMESTAMP = 2.0
FRAME_SHAPE = (4, 6, 3)
HAND_CONFIDENCE = 0.9
GESTURE_CONFIDENCE = 0.8
THUMB_OPEN_THRESHOLD = 0.5
OPEN_RATIO = 0.8
CLOSED_RATIO = 0.2
SHORT_POINTS = 5


def _point(x: float, y: float, z: float = 0.0) -> Point:
    return Point(x=x, y=y, z=z)


# Geometria de la mano de prueba: muneca (0.5, 0.75) y MCP del corazon
# (0.5, 0.5) dan escala 0.25 exacta; el pulgar se ubica a `ratio * 0.25` del
# MCP del indice sobre el eje x, asi el ratio de apertura es exactamente
# `ratio` para valores representables.
WRIST = _point(0.5, 0.75)
MIDDLE_MCP = _point(0.5, 0.5)
INDEX_MCP = _point(0.5, 0.5)
HAND_SCALE = 0.25


class RecordingBus:
    """Doble de EventBus que acumula los eventos publicados."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    def subscribe(self, event_type: type[EventT], handler: Callable[[EventT], None]) -> None:
        del event_type, handler

    def publish(self, event: DomainEvent) -> None:
        self.events.append(event)


def _hand(
    *,
    handedness: Handedness = Handedness.RIGHT,
    ratio: float = CLOSED_RATIO,
    points_count: int = HAND_LANDMARK_COUNT,
) -> HandLandmarks:
    points = [_point(0.5, 0.5)] * points_count
    if points_count == HAND_LANDMARK_COUNT:
        points[WRIST_LANDMARK_INDEX] = WRIST
        points[MIDDLE_FINGER_MCP_LANDMARK_INDEX] = MIDDLE_MCP
        points[INDEX_FINGER_MCP_LANDMARK_INDEX] = INDEX_MCP
        points[THUMB_TIP_LANDMARK_INDEX] = _point(0.5 - ratio * HAND_SCALE, 0.5)
    return HandLandmarks(
        handedness=handedness,
        confidence=HAND_CONFIDENCE,
        points=tuple(points),
    )


def _degenerate_hand() -> HandLandmarks:
    point = _point(0.5, 0.5)
    return HandLandmarks(
        handedness=Handedness.RIGHT,
        confidence=HAND_CONFIDENCE,
        points=(point,) * HAND_LANDMARK_COUNT,
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
) -> FrameContext:
    data: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    return FrameContext(
        frame=Frame(data=data, timestamp=timestamp),
        hands=hands,
        gestures=gestures,
    )


def _processor(
    bus: RecordingBus,
    *,
    activation_gesture: GestureId = GESTURE_POINTING_UP,
    thumb_open_threshold: float = THUMB_OPEN_THRESHOLD,
) -> PointerClickDetectionProcessor:
    return PointerClickDetectionProcessor(
        bus=bus,
        activation_gesture=activation_gesture,
        thumb_open_threshold=thumb_open_threshold,
    )


def _only_event(bus: RecordingBus) -> DomainEvent:
    assert len(bus.events) == 1
    return bus.events[0]


def test_thumb_open_emits_pointer_clicked() -> None:
    bus = RecordingBus()
    processor = _processor(bus)

    context = processor.process(
        _context(
            hands=(_hand(ratio=OPEN_RATIO),),
            gestures=(_gesture(),),
        )
    )

    event = _only_event(bus)
    assert isinstance(event, PointerClicked)
    assert processor.is_clicking is True
    assert context.clicking is True


def test_thumb_closed_no_event() -> None:
    bus = RecordingBus()
    processor = _processor(bus)

    context = processor.process(
        _context(
            hands=(_hand(ratio=CLOSED_RATIO),),
            gestures=(_gesture(),),
        )
    )

    assert bus.events == []
    assert processor.is_clicking is False
    assert context.clicking is False


def test_closing_thumb_emits_pointer_released() -> None:
    bus = RecordingBus()
    processor = _processor(bus)

    processor.process(
        _context(
            hands=(_hand(ratio=OPEN_RATIO),),
            gestures=(_gesture(),),
        )
    )
    assert processor.is_clicking is True

    context = processor.process(
        _context(
            hands=(_hand(ratio=CLOSED_RATIO),),
            gestures=(_gesture(),),
        )
    )

    assert processor.is_clicking is False
    assert context.clicking is False
    assert len(bus.events) == 2
    assert isinstance(bus.events[0], PointerClicked)
    assert isinstance(bus.events[1], PointerReleased)


def test_no_gesture_releases_if_was_clicking() -> None:
    bus = RecordingBus()
    processor = _processor(bus)

    processor.process(
        _context(
            hands=(_hand(ratio=OPEN_RATIO),),
            gestures=(_gesture(),),
        )
    )
    assert processor.is_clicking is True

    processor.process(_context(hands=(_hand(ratio=OPEN_RATIO),), gestures=()))

    assert processor.is_clicking is False
    assert len(bus.events) == 2
    assert isinstance(bus.events[0], PointerClicked)
    assert isinstance(bus.events[1], PointerReleased)


def test_two_hands_releases_if_was_clicking() -> None:
    bus = RecordingBus()
    processor = _processor(bus)

    processor.process(
        _context(
            hands=(_hand(ratio=OPEN_RATIO),),
            gestures=(_gesture(),),
        )
    )
    assert processor.is_clicking is True

    processor.process(
        _context(
            hands=(
                _hand(ratio=OPEN_RATIO),
                _hand(handedness=Handedness.LEFT, ratio=OPEN_RATIO),
            ),
            gestures=(_gesture(),),
        )
    )

    assert processor.is_clicking is False
    assert isinstance(bus.events[-1], PointerReleased)


def test_matching_hand_and_gesture_required() -> None:
    bus = RecordingBus()
    processor = _processor(bus)

    processor.process(
        _context(
            hands=(_hand(ratio=OPEN_RATIO),),
            gestures=(_gesture(handedness=Handedness.LEFT),),
        )
    )

    assert bus.events == []
    assert processor.is_clicking is False


def test_only_pointer_gesture_triggers_click() -> None:
    bus = RecordingBus()
    processor = _processor(bus, activation_gesture=GESTURE_VICTORY)

    processor.process(
        _context(
            hands=(_hand(ratio=OPEN_RATIO),),
            gestures=(_gesture(name=GESTURE_VICTORY),),
        )
    )

    event = _only_event(bus)
    assert isinstance(event, PointerClicked)


def test_other_gesture_does_not_trigger_click() -> None:
    bus = RecordingBus()
    processor = _processor(bus, activation_gesture=GESTURE_POINTING_UP)

    processor.process(
        _context(
            hands=(_hand(ratio=OPEN_RATIO),),
            gestures=(_gesture(name=GESTURE_VICTORY),),
        )
    )

    assert bus.events == []


def test_threshold_boundary_is_strict() -> None:
    bus = RecordingBus()
    processor = _processor(bus, thumb_open_threshold=0.5)

    # Justo en el umbral: no dispara.
    processor.process(
        _context(
            hands=(_hand(ratio=0.5),),
            gestures=(_gesture(),),
        )
    )
    assert bus.events == []
    assert processor.is_clicking is False

    # Por encima del umbral: dispara.
    processor.process(
        _context(
            hands=(_hand(ratio=0.5004),),
            gestures=(_gesture(),),
        )
    )
    assert len(bus.events) == 1
    assert isinstance(bus.events[0], PointerClicked)
    assert processor.is_clicking is True

    # De vuelta en el umbral: suelta.
    processor.process(
        _context(
            hands=(_hand(ratio=0.5),),
            gestures=(_gesture(),),
        )
    )
    assert len(bus.events) == 2
    assert isinstance(bus.events[1], PointerReleased)
    assert processor.is_clicking is False


def test_degenerate_hand_does_not_click() -> None:
    bus = RecordingBus()
    processor = _processor(bus)

    processor.process(
        _context(
            hands=(_degenerate_hand(),),
            gestures=(_gesture(),),
        )
    )

    assert bus.events == []
    assert processor.is_clicking is False


def test_incomplete_points_releases_if_was_clicking() -> None:
    bus = RecordingBus()
    processor = _processor(bus)

    processor.process(
        _context(
            hands=(_hand(ratio=OPEN_RATIO),),
            gestures=(_gesture(),),
        )
    )
    assert processor.is_clicking is True

    processor.process(
        _context(
            hands=(_hand(ratio=OPEN_RATIO, points_count=SHORT_POINTS),),
            gestures=(_gesture(),),
        )
    )

    assert processor.is_clicking is False
    assert len(bus.events) == 2
    assert isinstance(bus.events[1], PointerReleased)
