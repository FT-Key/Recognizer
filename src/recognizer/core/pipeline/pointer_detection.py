"""Processor que mapea la punta del indice al puntero cuando el gesto esta activo."""

from dataclasses import replace

from recognizer.core.domain.events import PointerMoved
from recognizer.core.domain.gesture import GestureId, StableGesture
from recognizer.core.domain.hand import (
    HAND_LANDMARK_COUNT,
    INDEX_FINGER_TIP_LANDMARK_INDEX,
    Handedness,
    HandLandmarks,
)
from recognizer.core.domain.pointer import PointerCalibration
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.pipeline.processor import Processor
from recognizer.core.pointer.smoothing import PointerSmoothing
from recognizer.core.ports.event_bus import EventBus


def _find_hand(
    *,
    hands: tuple[HandLandmarks, ...],
    handedness: Handedness,
) -> HandLandmarks | None:
    """Busca la mano con la lateralidad indicada (el core no importa el overlay)."""
    for hand in hands:
        if hand.handedness is handedness:
            return hand
    return None


class PointerDetectionProcessor(Processor):
    """Calcula el puntero desde la punta del indice del gesto de activacion."""

    def __init__(
        self,
        *,
        bus: EventBus,
        calibration: PointerCalibration,
        smoothing: PointerSmoothing,
        activation_gesture: GestureId,
    ) -> None:
        self._bus = bus
        self._calibration = calibration
        self._smoothing = smoothing
        self._activation_gesture = activation_gesture

    def process(self, context: FrameContext) -> FrameContext:
        """Publica PointerMoved y anota la posicion mientras el gesto siga activo."""
        gesture = self._find_gesture(context)
        hand = (
            None
            if gesture is None
            else _find_hand(hands=context.hands, handedness=gesture.handedness)
        )
        if hand is None or len(hand.points) != HAND_LANDMARK_COUNT:
            self._smoothing.reset()
            return replace(context, pointer=None)
        target = self._calibration.map(hand.points[INDEX_FINGER_TIP_LANDMARK_INDEX])
        position = self._smoothing.smooth(target)
        self._bus.publish(
            PointerMoved(timestamp=context.frame.timestamp, x=position.x, y=position.y)
        )
        return replace(context, pointer=position)

    def _find_gesture(self, context: FrameContext) -> StableGesture | None:
        for gesture in context.gestures:
            if gesture.name == self._activation_gesture:
                return gesture
        return None
