"""Tests del composition root: camara, acciones y pipeline."""

from collections.abc import Callable, Sequence
from typing import cast

import numpy as np
import pytest
from numpy.typing import NDArray

from recognizer import bootstrap
from recognizer.bootstrap import (
    build_action_bindings,
    build_pipeline,
    resolve_camera_config,
)
from recognizer.core.actions.decorators import GatedAction
from recognizer.core.config import (
    ActionConfig,
    ActionsConfig,
    AppConfig,
    CameraConfig,
    GestureConfig,
)
from recognizer.core.domain.action import ActionContext, MediaKey
from recognizer.core.domain.events import (
    DomainEvent,
    GestureDetected,
    HandsDetected,
)
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.gesture import (
    DetectedGesture,
    GestureName,
    GestureRecognition,
    StableGesture,
)
from recognizer.core.domain.hand import (
    HAND_LANDMARK_COUNT,
    Handedness,
    HandLandmarks,
    Point,
)
from recognizer.core.errors import ActionError, RecognizerError
from recognizer.core.ports.event_bus import EventT
from recognizer.core.ports.gesture_classifier import GestureClassifier

FRAME_TIMESTAMP = 2.0
FRAME_SHAPE = (4, 6, 3)
HAND_CONFIDENCE = 0.9
GESTURE_CONFIDENCE = 0.8
MIN_GESTURE_CONFIDENCE = 0.5
OVERRIDE_DEVICE_INDEX = 2
LONG_COOLDOWN_SECONDS = 1000.0


class RecordingKeySender:
    """Doble de KeySender que registra las pulsaciones recibidas."""

    def __init__(self) -> None:
        self.media: list[MediaKey] = []
        self.hotkeys: list[tuple[str, ...]] = []

    def press_media(self, key: MediaKey) -> None:
        self.media.append(key)

    def hotkey(self, keys: Sequence[str]) -> None:
        self.hotkeys.append(tuple(keys))


class RecordingCommandRunner:
    """Doble de CommandRunner que registra los argv recibidos."""

    def __init__(self) -> None:
        self.commands: list[tuple[str, ...]] = []

    def run(self, argv: Sequence[str]) -> None:
        self.commands.append(tuple(argv))


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
    data: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    return Frame(data=data, timestamp=FRAME_TIMESTAMP)


def _hand() -> HandLandmarks:
    point = Point(x=0.5, y=0.5, z=0.0)
    return HandLandmarks(
        handedness=Handedness.RIGHT,
        confidence=HAND_CONFIDENCE,
        points=(point,) * HAND_LANDMARK_COUNT,
    )


def _recognition() -> GestureRecognition:
    detection = DetectedGesture(
        name=GestureName.VICTORY,
        confidence=GESTURE_CONFIDENCE,
        handedness=Handedness.RIGHT,
    )
    return GestureRecognition(hands=(_hand(),), detections=(detection,))


def _context() -> ActionContext:
    return ActionContext(
        gesture=GestureName.VICTORY,
        confidence=GESTURE_CONFIDENCE,
        handedness=Handedness.RIGHT,
        timestamp=FRAME_TIMESTAMP,
    )


def _actions_config(*, cooldown: float = 0.0) -> ActionsConfig:
    return ActionsConfig.model_validate(
        {
            "cooldown_seconds": cooldown,
            "mappings": {
                "Thumb_Up": {"type": "media_key", "key": "volume_up"},
                "Victory": {"type": "hotkey", "keys": ["ctrl", "shift", "m"]},
                "ILoveYou": {"type": "command", "argv": ["notepad.exe"]},
            },
        }
    )


def test_resolve_camera_config_without_override_returns_config() -> None:
    app_config = AppConfig()

    assert resolve_camera_config(app_config=app_config, device_override=None) is app_config.camera


def test_resolve_camera_config_applies_override() -> None:
    app_config = AppConfig()

    resolved = resolve_camera_config(app_config=app_config, device_override=OVERRIDE_DEVICE_INDEX)

    assert resolved == CameraConfig(
        device_index=OVERRIDE_DEVICE_INDEX,
        width=app_config.camera.width,
        height=app_config.camera.height,
        target_fps=app_config.camera.target_fps,
    )


def test_resolve_camera_config_rejects_negative_override() -> None:
    with pytest.raises(RecognizerError, match="--device"):
        resolve_camera_config(app_config=AppConfig(), device_override=-1)


def test_build_action_bindings_without_mappings_is_empty() -> None:
    bindings = build_action_bindings(actions=ActionsConfig())

    assert bindings.mapping == {}
    assert bindings.gate is None


def test_build_action_bindings_routes_each_action_type() -> None:
    sender = RecordingKeySender()
    runner = RecordingCommandRunner()
    bindings = build_action_bindings(
        actions=_actions_config(),
        key_sender=sender,
        command_runner=runner,
    )
    context = _context()

    bindings.mapping[GestureName.THUMB_UP].execute(context)
    bindings.mapping[GestureName.VICTORY].execute(context)
    bindings.mapping[GestureName.I_LOVE_YOU].execute(context)

    assert sender.media == [MediaKey.VOLUME_UP]
    assert sender.hotkeys == [("ctrl", "shift", "m")]
    assert runner.commands == [("notepad.exe",)]


def test_build_action_bindings_shares_single_gate() -> None:
    sender = RecordingKeySender()
    runner = RecordingCommandRunner()
    bindings = build_action_bindings(
        actions=_actions_config(),
        key_sender=sender,
        command_runner=runner,
    )
    gate = bindings.gate

    assert gate is not None
    assert all(isinstance(action, GatedAction) for action in bindings.mapping.values())

    assert gate.toggle() is False
    bindings.mapping[GestureName.THUMB_UP].execute(_context())
    bindings.mapping[GestureName.VICTORY].execute(_context())
    bindings.mapping[GestureName.I_LOVE_YOU].execute(_context())
    assert sender.media == []
    assert sender.hotkeys == []
    assert runner.commands == []

    assert gate.toggle() is True
    bindings.mapping[GestureName.THUMB_UP].execute(_context())
    assert sender.media == [MediaKey.VOLUME_UP]


def test_build_action_bindings_debounces_with_cooldown() -> None:
    sender = RecordingKeySender()
    runner = RecordingCommandRunner()
    bindings = build_action_bindings(
        actions=_actions_config(cooldown=LONG_COOLDOWN_SECONDS),
        key_sender=sender,
        command_runner=runner,
    )
    action = bindings.mapping[GestureName.THUMB_UP]
    context = _context()

    action.execute(context)
    action.execute(context)
    action.execute(context)

    assert sender.media == [MediaKey.VOLUME_UP]


def test_build_action_rejects_unsupported_spec() -> None:
    # cast documentado: fuerza un spec fuera del union para cubrir el fallback.
    unsupported = cast(ActionConfig, object())

    with pytest.raises(ActionError, match="no soportada"):
        bootstrap._build_action(
            spec=unsupported,
            key_sender=RecordingKeySender(),
            command_runner=RecordingCommandRunner(),
        )


def test_build_pipeline_without_classifier_is_empty() -> None:
    bus = RecordingBus()
    pipeline = build_pipeline(classifier=None, bus=bus, gestures=GestureConfig())

    context = pipeline.run(_frame())

    assert context.hands == ()
    assert context.detections == ()
    assert context.gestures == ()
    assert bus.events == []


def test_build_pipeline_with_classifier_detects_and_stabilizes() -> None:
    recognition = _recognition()
    classifier: GestureClassifier = FakeClassifier(recognition)
    bus = RecordingBus()
    gestures = GestureConfig(
        stabilization_frames=1,
        min_gesture_confidence=MIN_GESTURE_CONFIDENCE,
    )
    pipeline = build_pipeline(classifier=classifier, bus=bus, gestures=gestures)
    frame = _frame()

    context = pipeline.run(frame)

    assert context.frame is frame
    assert context.hands == recognition.hands
    assert context.detections == recognition.detections
    assert context.gestures == (
        StableGesture(
            name=GestureName.VICTORY,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.RIGHT,
        ),
    )
    assert bus.events == [
        HandsDetected(timestamp=FRAME_TIMESTAMP, hands=recognition.hands),
        GestureDetected(
            timestamp=FRAME_TIMESTAMP,
            gesture=GestureName.VICTORY,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.RIGHT,
        ),
    ]
