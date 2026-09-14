"""Processor que detecta el pulgar abierto (click) y publica click/release.

Estando el puntero activo con Pointing_Up, el pulgar actua como boton: abrirlo
(forma de V con el indice) presiona el click y volver a cerrarlo lo suelta. El
indice no se mueve, asi el puntero se mantiene en el lugar donde se hace click.
"""

import logging
import math
from dataclasses import replace

from recognizer.core.constants import (
    MIN_VECTOR_NORM,
    POINTER_LOGGER_NAME,
    POINTER_MAX_VISIBLE_HANDS,
)
from recognizer.core.domain.events import PointerClicked, PointerReleased
from recognizer.core.domain.gesture import GestureId, StableGesture
from recognizer.core.domain.hand import (
    HAND_LANDMARK_COUNT,
    INDEX_FINGER_MCP_LANDMARK_INDEX,
    MIDDLE_FINGER_MCP_LANDMARK_INDEX,
    THUMB_TIP_LANDMARK_INDEX,
    WRIST_LANDMARK_INDEX,
    Handedness,
    HandLandmarks,
)
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.pipeline.processor import Processor
from recognizer.core.ports.event_bus import EventBus

logger = logging.getLogger(POINTER_LOGGER_NAME)


def _find_hand(
    *,
    hands: tuple[HandLandmarks, ...],
    handedness: Handedness,
) -> HandLandmarks | None:
    """Busca la mano con la lateralidad indicada."""
    for hand in hands:
        if hand.handedness is handedness:
            return hand
    return None


def _find_gesture(
    *,
    gestures: tuple[StableGesture, ...],
    activation_gesture: GestureId,
) -> StableGesture | None:
    """Busca el gesto de activacion del puntero."""
    for gesture in gestures:
        if gesture.name == activation_gesture:
            return gesture
    return None


def _thumb_open_ratio(hand: HandLandmarks) -> float:
    """Ratio de apertura del pulgar: distancia pulgar -> MCP del indice.

    Se divide por el tamano de la mano (muneca -> MCP del corazon) para no
    depender de lo lejos que este la mano de la camara. Pulgar abierto en V da
    un valor alto; pulgar cerrado contra la palma da un valor bajo. Una mano
    degenerada (escala ~0) devuelve 0.0.
    """
    wrist = hand.points[WRIST_LANDMARK_INDEX]
    middle_mcp = hand.points[MIDDLE_FINGER_MCP_LANDMARK_INDEX]
    scale = math.hypot(middle_mcp.x - wrist.x, middle_mcp.y - wrist.y)
    if scale < MIN_VECTOR_NORM:
        return 0.0
    thumb = hand.points[THUMB_TIP_LANDMARK_INDEX]
    index_mcp = hand.points[INDEX_FINGER_MCP_LANDMARK_INDEX]
    distance = math.hypot(thumb.x - index_mcp.x, thumb.y - index_mcp.y)
    return distance / scale


class PointerClickDetectionProcessor(Processor):
    """Detecta el pulgar abierto y publica PointerClicked/PointerReleased."""

    def __init__(
        self,
        *,
        bus: EventBus,
        activation_gesture: GestureId,
        thumb_open_threshold: float,
    ) -> None:
        self._bus = bus
        self._activation_gesture = activation_gesture
        self._thumb_open_threshold = thumb_open_threshold
        self._clicking = False

    def process(self, context: FrameContext) -> FrameContext:
        """Evalua el estado del click y publica eventos si hay cambio."""
        if len(context.hands) > POINTER_MAX_VISIBLE_HANDS:
            return self._release(context)

        gesture = _find_gesture(
            gestures=context.gestures,
            activation_gesture=self._activation_gesture,
        )
        if gesture is None:
            return self._release(context)

        hand = _find_hand(hands=context.hands, handedness=gesture.handedness)
        if hand is None or len(hand.points) != HAND_LANDMARK_COUNT:
            return self._release(context)

        ratio = _thumb_open_ratio(hand)
        logger.debug(
            "[CLICK] ratio=%.3f umbral=%.3f presionado=%s",
            ratio,
            self._thumb_open_threshold,
            self._clicking,
        )

        if not self._clicking and ratio > self._thumb_open_threshold:
            self._clicking = True
            self._bus.publish(PointerClicked(timestamp=context.frame.timestamp))
        elif self._clicking and ratio <= self._thumb_open_threshold:
            self._clicking = False
            self._bus.publish(PointerReleased(timestamp=context.frame.timestamp))

        return replace(context, clicking=self._clicking)

    def _release(self, context: FrameContext) -> FrameContext:
        """Suelta el click si estaba presionado y limpia el contexto."""
        if self._clicking:
            self._clicking = False
            self._bus.publish(PointerReleased(timestamp=context.frame.timestamp))
        return replace(context, clicking=False)

    @property
    def is_clicking(self) -> bool:
        """Indica si el click esta presionado actualmente."""
        return self._clicking
