"""Processor que estabiliza gestos por lateralidad y publica sus cambios."""

from dataclasses import dataclass, replace

from recognizer.core.domain.events import GestureDetected, GestureReleased
from recognizer.core.domain.gesture import (
    GESTURE_NONE,
    DetectedGesture,
    GestureId,
    StableGesture,
)
from recognizer.core.domain.hand import Handedness
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.pipeline.processor import Processor
from recognizer.core.ports.event_bus import EventBus

TRACKED_HANDEDNESSES: tuple[Handedness, ...] = (Handedness.LEFT, Handedness.RIGHT)
INITIAL_FRAME_COUNT = 0
INITIAL_CONFIDENCE = 0.0


@dataclass(slots=True)
class _SideState:
    """Estado de estabilizacion de una lateralidad."""

    confirmed: GestureId | None = None
    confidence: float = INITIAL_CONFIDENCE
    candidate: GestureId | None = None
    candidate_frames: int = INITIAL_FRAME_COUNT
    missing_frames: int = INITIAL_FRAME_COUNT

    def reset_pending(self) -> None:
        """Limpia el candidato y los contadores de ausencia."""
        self.candidate = None
        self.candidate_frames = INITIAL_FRAME_COUNT
        self.missing_frames = INITIAL_FRAME_COUNT

    def release(self) -> None:
        """Olvida el gesto confirmado preservando el candidato en curso."""
        self.confirmed = None
        self.confidence = INITIAL_CONFIDENCE
        self.missing_frames = INITIAL_FRAME_COUNT


class GestureStabilizerProcessor(Processor):
    """Confirma gestos tras N frames estables y los libera tras M ausencias."""

    def __init__(
        self,
        *,
        bus: EventBus,
        stabilization_frames: int,
        release_frames: int,
        min_gesture_confidence: float,
    ) -> None:
        self._bus = bus
        self._stabilization_frames = stabilization_frames
        self._release_frames = release_frames
        self._min_gesture_confidence = min_gesture_confidence
        self._states: dict[Handedness, _SideState] = {
            handedness: _SideState() for handedness in TRACKED_HANDEDNESSES
        }

    def process(self, context: FrameContext) -> FrameContext:
        """Actualiza el estado por lateralidad y publica los cambios."""
        observations = self._observations_by_side(context.detections)
        for handedness in TRACKED_HANDEDNESSES:
            self._advance(
                handedness=handedness,
                observation=observations.get(handedness),
                timestamp=context.frame.timestamp,
            )
        return replace(context, gestures=self._stable_gestures())

    def _observations_by_side(
        self,
        detections: tuple[DetectedGesture, ...],
    ) -> dict[Handedness, DetectedGesture]:
        """Indexa las detecciones validas por lateralidad.

        Si llegan varias detecciones de la misma lateralidad conserva la de
        mayor ``confidence``, no la ultima recibida.
        """
        observations: dict[Handedness, DetectedGesture] = {}
        for detection in detections:
            if detection.handedness is Handedness.UNKNOWN:
                continue
            if detection.name == GESTURE_NONE:
                continue
            if detection.confidence < self._min_gesture_confidence:
                continue
            current = observations.get(detection.handedness)
            if current is None or detection.confidence > current.confidence:
                observations[detection.handedness] = detection
        return observations

    def _advance(
        self,
        *,
        handedness: Handedness,
        observation: DetectedGesture | None,
        timestamp: float,
    ) -> None:
        state = self._states[handedness]

        if observation is not None and state.confirmed == observation.name:
            state.confidence = observation.confidence
            state.reset_pending()
            return

        if observation is not None:
            if state.candidate == observation.name:
                state.candidate_frames += 1
            else:
                state.candidate = observation.name
                state.candidate_frames = 1
            if state.candidate_frames >= self._stabilization_frames:
                self._confirm(
                    handedness=handedness,
                    observation=observation,
                    state=state,
                    timestamp=timestamp,
                )
                return
        else:
            state.candidate = None
            state.candidate_frames = INITIAL_FRAME_COUNT

        if state.confirmed is not None:
            state.missing_frames += 1
            if state.missing_frames >= self._release_frames:
                self._bus.publish(
                    GestureReleased(
                        timestamp=timestamp,
                        gesture=state.confirmed,
                        handedness=handedness,
                    )
                )
                state.release()

    def _confirm(
        self,
        *,
        handedness: Handedness,
        observation: DetectedGesture,
        state: _SideState,
        timestamp: float,
    ) -> None:
        previous = state.confirmed
        if previous is not None and previous != observation.name:
            self._bus.publish(
                GestureReleased(timestamp=timestamp, gesture=previous, handedness=handedness)
            )
        self._bus.publish(
            GestureDetected(
                timestamp=timestamp,
                gesture=observation.name,
                confidence=observation.confidence,
                handedness=handedness,
            )
        )
        state.confirmed = observation.name
        state.confidence = observation.confidence
        state.reset_pending()

    def _stable_gestures(self) -> tuple[StableGesture, ...]:
        gestures: list[StableGesture] = []
        for handedness in TRACKED_HANDEDNESSES:
            state = self._states[handedness]
            if state.confirmed is not None:
                gestures.append(
                    StableGesture(
                        name=state.confirmed,
                        confidence=state.confidence,
                        handedness=handedness,
                    )
                )
        return tuple(gestures)
