"""Tests del composition root: camara, acciones y pipeline."""

from collections.abc import Callable, Sequence
from typing import cast

import numpy as np
import pytest
from numpy.typing import NDArray

from recognizer import bootstrap
from recognizer.adapters.overlay_opencv import GestureOverlay, LandmarkOverlay, PointerOverlay
from recognizer.bootstrap import (
    build_action_bindings,
    build_pipeline,
    build_pointer_mover,
    resolve_camera_config,
)
from recognizer.core.actions.decorators import ActionGate, GatedAction
from recognizer.core.actions.links import OpenLinksAction
from recognizer.core.actions.script import ScriptAction
from recognizer.core.config import (
    ActionConfig,
    ActionsConfig,
    AppConfig,
    CameraConfig,
    GestureConfig,
    GestureRuleConfig,
    OpenLinksActionConfig,
    PointerConfig,
    ScriptActionConfig,
)
from recognizer.core.constants import CONTEXT_ENV_GESTURE
from recognizer.core.domain.action import ActionContext, MediaKey, ScriptInterpreter, ScriptRequest
from recognizer.core.domain.events import (
    DomainEvent,
    GestureDetected,
    HandsDetected,
    PointerMoved,
)
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.gesture import (
    GESTURE_ILOVE_YOU,
    GESTURE_THUMB_UP,
    GESTURE_VICTORY,
    DetectedGesture,
    Finger,
    GestureCatalog,
    GestureId,
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
from recognizer.core.pipeline.gesture_detection import GestureDetectionProcessor
from recognizer.core.pipeline.gesture_stabilization import GestureStabilizerProcessor
from recognizer.core.pipeline.landmark_rules import LandmarkRuleProcessor
from recognizer.core.pipeline.pointer_detection import PointerDetectionProcessor
from recognizer.core.pointer.mover import PointerMover
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


class RecordingMouseController:
    """Doble de MouseController que registra los movimientos recibidos."""

    def __init__(self) -> None:
        self.moves: list[tuple[float, float]] = []

    def move_to(self, *, x: float, y: float) -> None:
        self.moves.append((x, y))


class RecordingScriptRunner:
    """Doble de ScriptRunner que registra los requests recibidos."""

    def __init__(self) -> None:
        self.requests: list[ScriptRequest] = []

    def run(self, request: ScriptRequest) -> None:
        self.requests.append(request)


class RecordingLinkOpener:
    """Doble de LinkOpener que registra las URLs abiertas."""

    def __init__(self) -> None:
        self.urls: list[str] = []

    def open(self, url: str) -> None:
        self.urls.append(url)


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
        name=GESTURE_VICTORY,
        confidence=GESTURE_CONFIDENCE,
        handedness=Handedness.RIGHT,
    )
    return GestureRecognition(hands=(_hand(),), detections=(detection,))


def _catalog() -> GestureCatalog:
    return GestureCatalog.from_labels(custom_labels=(), rule_names=())


def _context() -> ActionContext:
    return ActionContext(
        gesture=GESTURE_VICTORY,
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
    bindings = build_action_bindings(actions=ActionsConfig(), catalog=_catalog())

    assert bindings.mapping == {}
    assert bindings.gate is None


def test_build_action_bindings_routes_each_action_type() -> None:
    sender = RecordingKeySender()
    runner = RecordingCommandRunner()
    bindings = build_action_bindings(
        actions=_actions_config(),
        catalog=_catalog(),
        key_sender=sender,
        command_runner=runner,
    )
    context = _context()

    bindings.mapping[GESTURE_THUMB_UP].execute(context)
    bindings.mapping[GESTURE_VICTORY].execute(context)
    bindings.mapping[GESTURE_ILOVE_YOU].execute(context)

    assert sender.media == [MediaKey.VOLUME_UP]
    assert sender.hotkeys == [("ctrl", "shift", "m")]
    assert runner.commands == [("notepad.exe",)]


def test_build_action_bindings_shares_single_gate() -> None:
    sender = RecordingKeySender()
    runner = RecordingCommandRunner()
    bindings = build_action_bindings(
        actions=_actions_config(),
        catalog=_catalog(),
        key_sender=sender,
        command_runner=runner,
    )
    gate = bindings.gate

    assert gate is not None
    assert all(isinstance(action, GatedAction) for action in bindings.mapping.values())

    assert gate.toggle() is False
    bindings.mapping[GESTURE_THUMB_UP].execute(_context())
    bindings.mapping[GESTURE_VICTORY].execute(_context())
    bindings.mapping[GESTURE_ILOVE_YOU].execute(_context())
    assert sender.media == []
    assert sender.hotkeys == []
    assert runner.commands == []

    assert gate.toggle() is True
    bindings.mapping[GESTURE_THUMB_UP].execute(_context())
    assert sender.media == [MediaKey.VOLUME_UP]


def test_build_action_bindings_debounces_with_cooldown() -> None:
    sender = RecordingKeySender()
    runner = RecordingCommandRunner()
    bindings = build_action_bindings(
        actions=_actions_config(cooldown=LONG_COOLDOWN_SECONDS),
        catalog=_catalog(),
        key_sender=sender,
        command_runner=runner,
    )
    action = bindings.mapping[GESTURE_THUMB_UP]
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
            script_runner=RecordingScriptRunner(),
            link_opener=RecordingLinkOpener(),
        )


def test_build_action_builds_script_action_with_injected_runner() -> None:
    runner = RecordingScriptRunner()
    spec = ScriptActionConfig(path="scripts/celebrate.py", pass_context=True)

    action = bootstrap._build_action(
        spec=spec,
        key_sender=RecordingKeySender(),
        command_runner=RecordingCommandRunner(),
        script_runner=runner,
        link_opener=RecordingLinkOpener(),
    )

    assert isinstance(action, ScriptAction)
    action.execute(_context())
    assert len(runner.requests) == 1
    assert runner.requests[0].path == "scripts/celebrate.py"


def test_build_action_builds_open_links_with_injected_opener() -> None:
    opener = RecordingLinkOpener()
    spec = OpenLinksActionConfig(urls=("https://a.example", "https://b.example"))

    action = bootstrap._build_action(
        spec=spec,
        key_sender=RecordingKeySender(),
        command_runner=RecordingCommandRunner(),
        script_runner=RecordingScriptRunner(),
        link_opener=opener,
    )

    assert isinstance(action, OpenLinksAction)
    action.execute(_context())
    action.execute(_context())
    assert opener.urls == ["https://a.example", "https://b.example"]


def test_build_action_uses_browser_as_chrome_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[str | None] = []

    class FakeChromeLinkOpener:
        """Doble de ChromeLinkOpener que registra el ejecutable inyectado."""

        def __init__(self, *, executable: str | None = None) -> None:
            created.append(executable)

        def open(self, url: str) -> None:
            del url

    monkeypatch.setattr(bootstrap, "ChromeLinkOpener", FakeChromeLinkOpener)
    spec = OpenLinksActionConfig(urls=("https://a.example",), browser="C:\\chrome.exe")

    action = bootstrap._build_action(
        spec=spec,
        key_sender=RecordingKeySender(),
        command_runner=RecordingCommandRunner(),
        script_runner=RecordingScriptRunner(),
        link_opener=RecordingLinkOpener(),
    )

    assert isinstance(action, OpenLinksAction)
    assert created == ["C:\\chrome.exe"]


def test_build_action_bindings_routes_script_mapping() -> None:
    runner = RecordingScriptRunner()
    actions = ActionsConfig.model_validate(
        {
            "mappings": {
                "Victory": {
                    "type": "script",
                    "path": "scripts/celebrate.py",
                    "args": ["--loud"],
                    "interpreter": "python",
                    "working_dir": "scripts",
                    "blocking": True,
                    "timeout_seconds": 3.0,
                    "pass_context": True,
                }
            }
        }
    )

    bindings = build_action_bindings(
        actions=actions,
        catalog=_catalog(),
        key_sender=RecordingKeySender(),
        command_runner=RecordingCommandRunner(),
        script_runner=runner,
    )

    bindings.mapping[GESTURE_VICTORY].execute(_context())

    assert len(runner.requests) == 1
    request = runner.requests[0]
    assert request.path == "scripts/celebrate.py"
    assert request.args == ("--loud",)
    assert request.interpreter is ScriptInterpreter.PYTHON
    assert request.working_dir == "scripts"
    assert request.blocking is True
    assert request.timeout_seconds == 3.0
    assert request.env is not None
    assert request.env[CONTEXT_ENV_GESTURE] == GESTURE_VICTORY.value


def test_build_action_bindings_routes_open_links_mapping() -> None:
    opener = RecordingLinkOpener()
    actions = ActionsConfig.model_validate(
        {
            "mappings": {
                "ILoveYou": {
                    "type": "open_links",
                    "urls": ["https://a.example", "https://b.example"],
                }
            }
        }
    )

    bindings = build_action_bindings(
        actions=actions,
        catalog=_catalog(),
        key_sender=RecordingKeySender(),
        command_runner=RecordingCommandRunner(),
        script_runner=RecordingScriptRunner(),
        link_opener=opener,
    )

    bindings.mapping[GESTURE_ILOVE_YOU].execute(_context())

    assert opener.urls == ["https://a.example"]


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
            name=GESTURE_VICTORY,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.RIGHT,
        ),
    )
    assert bus.events == [
        HandsDetected(timestamp=FRAME_TIMESTAMP, hands=recognition.hands),
        GestureDetected(
            timestamp=FRAME_TIMESTAMP,
            gesture=GESTURE_VICTORY,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.RIGHT,
        ),
    ]


def test_build_pipeline_with_rules_appends_rule_processor() -> None:
    gestures = GestureConfig(
        stabilization_frames=1,
        rules={"L_Sign": GestureRuleConfig(extended=(Finger.INDEX,))},
    )
    pipeline = build_pipeline(
        classifier=FakeClassifier(_recognition()),
        bus=RecordingBus(),
        gestures=gestures,
    )

    types = [type(processor) for processor in pipeline.processors]

    assert types[:3] == [
        GestureDetectionProcessor,
        LandmarkRuleProcessor,
        GestureStabilizerProcessor,
    ]


@pytest.mark.parametrize("pointer", [None, PointerConfig(enabled=False)])
def test_build_pipeline_omits_pointer_processors_when_inactive(
    pointer: PointerConfig | None,
) -> None:
    pipeline = build_pipeline(
        classifier=FakeClassifier(_recognition()),
        bus=RecordingBus(),
        gestures=GestureConfig(stabilization_frames=1),
        pointer=pointer,
    )

    assert not any(
        isinstance(processor, (PointerDetectionProcessor, PointerOverlay))
        for processor in pipeline.processors
    )


def test_build_pipeline_with_pointer_appends_detector_and_overlay_last() -> None:
    pipeline = build_pipeline(
        classifier=FakeClassifier(_recognition()),
        bus=RecordingBus(),
        gestures=GestureConfig(stabilization_frames=1),
        pointer=PointerConfig(),
    )

    types = [type(processor) for processor in pipeline.processors]

    assert types == [
        GestureDetectionProcessor,
        GestureStabilizerProcessor,
        PointerDetectionProcessor,
        LandmarkOverlay,
        GestureOverlay,
        PointerOverlay,
    ]


def test_build_pipeline_without_classifier_ignores_pointer() -> None:
    pipeline = build_pipeline(
        classifier=None,
        bus=RecordingBus(),
        gestures=GestureConfig(),
        pointer=PointerConfig(),
    )

    assert pipeline.processors == ()


def test_build_pipeline_pointer_detection_runs_when_gesture_is_active() -> None:
    bus = RecordingBus()
    pipeline = build_pipeline(
        classifier=FakeClassifier(_recognition()),
        bus=bus,
        gestures=GestureConfig(
            stabilization_frames=1,
            min_gesture_confidence=MIN_GESTURE_CONFIDENCE,
        ),
        pointer=PointerConfig(activation_gesture=GESTURE_VICTORY.value),
    )

    context = pipeline.run(_frame())

    assert context.pointer is not None
    assert context.pointer.x == pytest.approx(0.5)
    assert context.pointer.y == pytest.approx(0.5)
    assert len(bus.events) == 3
    event = bus.events[-1]
    assert isinstance(event, PointerMoved)
    assert event.x == pytest.approx(0.5)
    assert event.y == pytest.approx(0.5)


def test_build_pointer_mover_returns_none_when_disabled() -> None:
    assert build_pointer_mover(pointer=PointerConfig(enabled=False)) is None


def test_build_pointer_mover_returns_mover_with_controller() -> None:
    controller = RecordingMouseController()

    mover = build_pointer_mover(pointer=PointerConfig(), controller=controller)

    assert isinstance(mover, PointerMover)
    mover.handle(PointerMoved(timestamp=FRAME_TIMESTAMP, x=0.25, y=0.75))
    assert controller.moves == [(0.25, 0.75)]


def test_build_action_bindings_without_mappings_reuses_gate() -> None:
    gate = ActionGate()

    bindings = build_action_bindings(actions=ActionsConfig(), catalog=_catalog(), gate=gate)

    assert bindings.mapping == {}
    assert bindings.gate is gate


def test_build_action_bindings_with_mappings_reuses_gate() -> None:
    gate = ActionGate()

    bindings = build_action_bindings(
        actions=_actions_config(),
        catalog=_catalog(),
        key_sender=RecordingKeySender(),
        command_runner=RecordingCommandRunner(),
        gate=gate,
    )

    assert bindings.gate is gate


def test_build_action_bindings_resolves_custom_catalog_labels() -> None:
    catalog = GestureCatalog.from_labels(custom_labels=("Custom_Wave",), rule_names=())
    actions = ActionsConfig.model_validate(
        {"mappings": {"Custom_Wave": {"type": "hotkey", "keys": ["ctrl", "m"]}}}
    )
    sender = RecordingKeySender()
    bindings = build_action_bindings(
        actions=actions,
        catalog=catalog,
        key_sender=sender,
        command_runner=RecordingCommandRunner(),
    )

    bindings.mapping[GestureId("Custom_Wave")].execute(_context())

    assert sender.hotkeys == [("ctrl", "m")]
