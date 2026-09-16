"""Tests del CLI de la app local, sin camara real ni acciones externas."""

import logging
import sys
import tempfile
import threading
from collections import Counter
from pathlib import Path
from typing import ClassVar, cast

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray

from recognizer.bootstrap import ActionBindings
from recognizer.cli import app
from recognizer.cli.runtime import RuntimeCallbacks
from recognizer.core.actions.decorators import ActionGate
from recognizer.core.actions.menus import Menu
from recognizer.core.bus import InProcessEventBus
from recognizer.core.config import (
    ActionsConfig,
    AppConfig,
    MediaKeyActionConfig,
    MenuConfig,
    PointerConfig,
)
from recognizer.core.domain.action import ActionContext, MediaKey
from recognizer.core.domain.events import (
    DomainEvent,
    GestureDetected,
    GestureReleased,
    HandsDetected,
    PointerMoved,
)
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.gesture import (
    GESTURE_OPEN_PALM,
    GESTURE_POINTING_UP,
    GESTURE_VICTORY,
    GestureId,
)
from recognizer.core.domain.hand import Handedness, HandLandmarks, Point
from recognizer.core.pipeline.builder import Pipeline
from recognizer.core.pipeline.context import FrameContext

EXPECTED_FAILURE_CODE = 1
GESTURE_CONFIDENCE = 0.8
HAND_CONFIDENCE = 0.9
TWO_HANDS = 2
DEFAULT_CONFIG = Path("config.yaml")
HUD_FRAME_WIDTH = 20
HUD_FRAME_HEIGHT = 10


def _hand() -> HandLandmarks:
    return HandLandmarks(
        handedness=Handedness.RIGHT,
        confidence=HAND_CONFIDENCE,
        points=(Point(x=0.5, y=0.5, z=0.0),),
    )


def test_parser_defaults() -> None:
    args = app._build_parser().parse_args([])

    assert args.config == DEFAULT_CONFIG
    assert args.device is None
    assert args.frames == 0
    assert args.no_window is False
    assert args.no_actions is False
    assert args.no_pointer is False
    assert args.verbose is False
    assert args.health_port == app.DEFAULT_HEALTH_PORT_SOURCE


def test_default_health_port_is_disabled_in_source() -> None:
    assert app._default_health_port() == app.DEFAULT_HEALTH_PORT_SOURCE
    assert app._default_config_path() == DEFAULT_CONFIG
    assert app._is_frozen() is False


def test_default_log_file_is_none_in_source() -> None:
    assert app._default_log_file() is None


def test_log_file_flag_is_parsed(tmp_path: Path) -> None:
    target = tmp_path / "custom.log"
    args = app._build_parser().parse_args(["--log-file", str(target)])

    assert args.log_file == target


def test_configure_logging_writes_to_file(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "recognizer.log"
    root = logging.getLogger()
    before = list(root.handlers)

    try:
        resolved = app._configure_logging(verbose=False, log_file=log_path)
        assert resolved == log_path
        logging.getLogger("recognizer.test").warning("mensaje de prueba")
        for handler in root.handlers:
            handler.flush()
        assert log_path.is_file()
        assert "mensaje de prueba" in log_path.read_text(encoding="utf-8")
    finally:
        for handler in list(root.handlers):
            if handler not in before:
                root.removeHandler(handler)
                handler.close()


def test_configure_logging_without_file_returns_none() -> None:
    assert app._configure_logging(verbose=False, log_file=None) is None


def test_log_screen_size_logs_dimensions(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(app, "screen_size", lambda: (1920, 1080))

    with caplog.at_level(logging.INFO, logger=app.LOGGER.name):
        app._log_screen_size()

    assert any("1920x1080" in record.getMessage() for record in caplog.records)


def test_log_screen_size_logs_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def failing_screen_size() -> tuple[int, int]:
        msg = "sin tk"
        raise RuntimeError(msg)

    monkeypatch.setattr(app, "screen_size", failing_screen_size)

    with caplog.at_level(logging.ERROR, logger=app.LOGGER.name):
        app._log_screen_size()

    assert any(record.levelno == logging.ERROR for record in caplog.records)


def test_install_exception_hooks_logs_unhandled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    original_sys_hook = sys.excepthook
    original_thread_hook = threading.excepthook

    try:
        app._install_exception_hooks(app.LOGGER)
        with caplog.at_level(logging.CRITICAL, logger=app.LOGGER.name):
            sys.excepthook(RuntimeError, RuntimeError("boom"), None)

        assert any("no controlada" in record.getMessage().lower() for record in caplog.records)
    finally:
        sys.excepthook = original_sys_hook
        threading.excepthook = original_thread_hook


def test_resolve_log_file_falls_back_to_temp_when_unwritable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    blocked = tmp_path / "readonly"
    original_mkdir = Path.mkdir

    def selective_mkdir(
        self: Path,
        mode: int = 0o777,
        parents: bool = False,
        exist_ok: bool = False,
    ) -> None:
        if self == blocked:
            msg = "read-only"
            raise OSError(msg)
        original_mkdir(self, mode=mode, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(Path, "mkdir", selective_mkdir)

    resolved = app._resolve_log_file(blocked / "recognizer.log")

    assert resolved.parent == Path(tempfile.gettempdir()) / app.LOGS_DIRNAME


def test_health_port_flag_is_parsed() -> None:
    args = app._build_parser().parse_args(["--health-port", "9000"])

    assert args.health_port == 9000


class FakeHealthServer:
    """Doble del servidor de salud que registra arranque y parada."""

    instances: ClassVar[list["FakeHealthServer"]] = []

    def __init__(self, *, port: int, app_name: str, version: str) -> None:
        self.port_arg = port
        self.app_name = app_name
        self.version = version
        self.started = False
        self.stopped = False
        FakeHealthServer.instances.append(self)

    def start(self) -> int:
        self.started = True
        return self.port_arg

    def stop(self) -> None:
        self.stopped = True


def test_main_with_health_port_starts_and_stops_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    moves: list[object] = []
    _patch_main_dependencies(monkeypatch, captured=captured, moves=moves)
    FakeHealthServer.instances = []
    monkeypatch.setattr(app, "HealthServer", FakeHealthServer)

    result = app.main(["--no-window", "--frames", "1", "--health-port", "9100"])

    assert result == 0
    assert len(FakeHealthServer.instances) == 1
    instance = FakeHealthServer.instances[0]
    assert instance.port_arg == 9100
    assert instance.app_name == app.APP_NAME
    assert instance.started is True
    assert instance.stopped is True


def test_main_without_health_port_does_not_start_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    moves: list[object] = []
    _patch_main_dependencies(monkeypatch, captured=captured, moves=moves)
    FakeHealthServer.instances = []
    monkeypatch.setattr(app, "HealthServer", FakeHealthServer)

    result = app.main(["--no-window", "--frames", "1"])

    assert result == 0
    assert FakeHealthServer.instances == []


def test_parser_reads_all_flags() -> None:
    args = app._build_parser().parse_args(
        [
            "--config",
            "otra.yaml",
            "--device",
            "2",
            "--frames",
            "10",
            "--no-window",
            "--no-actions",
            "--no-pointer",
            "--verbose",
        ]
    )

    assert args.config == Path("otra.yaml")
    assert args.device == 2
    assert args.frames == 10
    assert args.no_window is True
    assert args.no_actions is True
    assert args.no_pointer is True
    assert args.verbose is True


def test_no_window_without_frames_fails_before_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(path: Path) -> object:
        del path
        msg = "load_config no debe llamarse sin --frames."
        raise AssertionError(msg)

    class FailingCamera:
        """Doble que falla si la app intenta abrir la camara."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs
            msg = "La camara no debe abrirse sin --frames."
            raise AssertionError(msg)

    monkeypatch.setattr(app, "load_config", fail_if_called)
    monkeypatch.setattr(app, "OpenCVCamera", FailingCamera)

    assert app.main(["--no-window"]) == EXPECTED_FAILURE_CODE


def test_stats_handle_updates_counters() -> None:
    stats = app._Stats()
    hand = _hand()

    stats.handle(HandsDetected(timestamp=0.1, hands=(hand,)))
    stats.handle(HandsDetected(timestamp=0.2, hands=(hand, hand)))
    stats.handle(
        GestureDetected(
            timestamp=0.3,
            gesture=GESTURE_VICTORY,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.RIGHT,
        )
    )
    stats.handle(
        GestureDetected(
            timestamp=0.4,
            gesture=GESTURE_VICTORY,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.RIGHT,
        )
    )
    stats.handle(
        GestureDetected(
            timestamp=0.5,
            gesture=GESTURE_OPEN_PALM,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.LEFT,
        )
    )
    stats.handle(
        GestureReleased(
            timestamp=0.6,
            gesture=GESTURE_VICTORY,
            handedness=Handedness.RIGHT,
        )
    )
    stats.handle(PointerMoved(timestamp=0.7, x=0.25, y=0.75))

    assert stats.hands_events == 2
    assert stats.max_hands == TWO_HANDS
    assert stats.detected_events == 3
    assert stats.released_events == 1
    assert stats.pointer_events == 1
    assert stats.confirmed == {GESTURE_VICTORY: 2, GESTURE_OPEN_PALM: 1}


def test_actions_state_without_gate_is_inactive() -> None:
    assert app._actions_state(None) == "inactivas"


def test_actions_state_reflects_gate() -> None:
    gate = ActionGate()

    assert app._actions_state(gate) == "activadas"
    gate.toggle()
    assert app._actions_state(gate) == "desactivadas"


def test_format_confirmed_without_gestures() -> None:
    assert app._format_confirmed(Counter()) == app.NO_CONFIRMED_GESTURES


def test_format_confirmed_lists_counts() -> None:
    confirmed: Counter[GestureId] = Counter({GESTURE_VICTORY: 2, GESTURE_OPEN_PALM: 1})

    assert app._format_confirmed(confirmed) == "Victory=2, Open_Palm=1"


def test_pointer_state_reflects_flag() -> None:
    assert app._pointer_state(True) == "activado"
    assert app._pointer_state(False) == "desactivado"


class FakeCamera:
    """Doble de camara que solo satisface el protocolo de context manager."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs

    def __enter__(self) -> "FakeCamera":
        return self

    def __exit__(self, *args: object) -> None:
        del args


class FakeClassifier:
    """Doble del clasificador que solo satisface el context manager."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs

    def __enter__(self) -> "FakeClassifier":
        return self

    def __exit__(self, *args: object) -> None:
        del args


class FakeMover:
    """Doble del mover del puntero que registra los eventos recibidos."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    def handle(self, event: DomainEvent) -> None:
        self.events.append(event)


def _patch_main_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    captured: dict[str, object],
    moves: list[object],
    app_config: AppConfig | None = None,
) -> AppConfig:
    config = (
        app_config if app_config is not None else AppConfig(pointer=PointerConfig(enabled=True))
    )

    def fake_build_pipeline(
        *,
        classifier: object,
        bus: object,
        gestures: object,
        pointer: object = None,
        catalog: object = None,
        menus: object = None,
        repeat_intervals: object = None,
    ) -> Pipeline:
        del classifier, gestures, catalog, repeat_intervals
        captured["bus"] = bus
        captured["pipeline_pointer"] = pointer
        captured["menus"] = menus
        return Pipeline(processors=())

    def fake_build_pointer_mover(
        *,
        pointer: object,
        gate: object = None,
        controller: object = None,
        logger: object = None,
    ) -> FakeMover:
        del controller, logger
        captured["mover_gate"] = gate
        moves.append(pointer)
        mover = FakeMover()
        captured["mover"] = mover
        return mover

    def fake_run_camera_loop(
        camera: object,
        *,
        pipeline: object,
        window_name: str,
        show_window: bool,
        max_frames: int,
        callbacks: object = None,
    ) -> tuple[int, float]:
        del camera, pipeline, window_name, show_window, max_frames
        captured["callbacks"] = callbacks
        return (1, 30.0)

    monkeypatch.setattr(app, "load_config", lambda _path: config)
    monkeypatch.setattr(app, "OpenCVCamera", FakeCamera)
    monkeypatch.setattr(app, "MediaPipeGestureClassifier", FakeClassifier)
    monkeypatch.setattr(app, "build_pipeline", fake_build_pipeline)
    monkeypatch.setattr(app, "build_pointer_mover", fake_build_pointer_mover)
    monkeypatch.setattr(app, "run_camera_loop", fake_run_camera_loop)
    return config


def test_main_with_pointer_enabled_wires_mover_and_reports(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    captured: dict[str, object] = {}
    moves: list[object] = []
    app_config = _patch_main_dependencies(monkeypatch, captured=captured, moves=moves)
    caplog.set_level(logging.INFO, logger=app.LOGGER.name)

    result = app.main(["--no-window", "--frames", "1"])

    assert result == 0
    assert captured["pipeline_pointer"] is app_config.pointer
    assert isinstance(captured["mover_gate"], ActionGate)
    assert moves == [app_config.pointer]
    assert "PointerMoved: 0" in caplog.text
    assert "Puntero: activado" in caplog.text


def test_main_with_no_pointer_flag_disables_pointer(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    captured: dict[str, object] = {}
    moves: list[object] = []
    _patch_main_dependencies(monkeypatch, captured=captured, moves=moves)
    caplog.set_level(logging.INFO, logger=app.LOGGER.name)

    result = app.main(["--no-window", "--frames", "1", "--no-pointer"])

    assert result == 0
    assert captured["pipeline_pointer"] is None
    assert moves == []
    assert "Puntero: desactivado" in caplog.text


def test_pointer_moved_on_real_bus_reaches_subscribed_mover(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    moves: list[object] = []
    _patch_main_dependencies(monkeypatch, captured=captured, moves=moves)

    result = app.main(["--no-window", "--frames", "1"])

    assert result == 0
    bus = cast(InProcessEventBus, captured["bus"])
    mover = cast(FakeMover, captured["mover"])
    event = PointerMoved(timestamp=1.0, x=0.25, y=0.75)

    bus.publish(event)

    assert mover.events == [event]


def test_main_no_actions_with_pointer_uses_pointer_hud_and_toggle_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    moves: list[object] = []
    app_config = AppConfig(
        pointer=PointerConfig(enabled=True),
        actions=ActionsConfig(mappings={"Victory": MediaKeyActionConfig(key=MediaKey.VOLUME_UP)}),
    )
    _patch_main_dependencies(monkeypatch, captured=captured, moves=moves, app_config=app_config)

    def fail_build_action_bindings(**kwargs: object) -> object:
        del kwargs
        msg = "build_action_bindings no debe llamarse con --no-actions."
        raise AssertionError(msg)

    monkeypatch.setattr(app, "build_action_bindings", fail_build_action_bindings)
    texts: list[str] = []

    def fake_put_text(
        image: NDArray[np.uint8],
        text: str,
        org: tuple[int, int],
        font: int,
        scale: float,
        color: tuple[int, int, int],
        thickness: int,
    ) -> None:
        del image, org, font, scale, color, thickness
        texts.append(text)

    monkeypatch.setattr(cv2, "putText", fake_put_text)

    result = app.main(["--no-window", "--frames", "1", "--no-actions"])

    assert result == 0
    assert moves == [app_config.pointer]
    callbacks = cast(RuntimeCallbacks, captured["callbacks"])
    gate = cast(ActionGate, captured["mover_gate"])
    assert callbacks.on_context is not None
    assert callbacks.on_key is not None
    frame_data: NDArray[np.uint8] = np.zeros((HUD_FRAME_HEIGHT, HUD_FRAME_WIDTH, 3), dtype=np.uint8)
    context = FrameContext(frame=Frame(data=frame_data, timestamp=0.0))

    callbacks.on_context(context)
    assert gate.enabled is True
    callbacks.on_key(app.TOGGLE_KEY)
    callbacks.on_context(context)

    assert gate.enabled is False
    assert texts == [app.HUD_POINTER_ENABLED_TEXT, app.HUD_POINTER_DISABLED_TEXT]


class RecordingAction:
    """Doble de Action que registra los contextos ejecutados."""

    def __init__(self) -> None:
        self.contexts: list[ActionContext] = []

    def execute(self, context: ActionContext) -> None:
        self.contexts.append(context)


def test_main_with_menus_only_wires_dispatcher_and_menu_overlay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    moves: list[object] = []
    app_config = AppConfig(
        pointer=PointerConfig(enabled=False),
        actions=ActionsConfig(
            menus={
                "Replay": MenuConfig(
                    hand=Handedness.LEFT,
                    modifier=GESTURE_POINTING_UP.value,
                    options={"Victory": MediaKeyActionConfig(key=MediaKey.VOLUME_UP)},
                )
            }
        ),
    )
    _patch_main_dependencies(monkeypatch, captured=captured, moves=moves, app_config=app_config)

    menu_action = RecordingAction()
    menu = Menu(
        name="Replay",
        hand=Handedness.LEFT,
        modifier=GESTURE_POINTING_UP,
        consume_trigger=True,
        options={GESTURE_VICTORY: menu_action},
    )
    bindings = ActionBindings(mapping={}, gate=ActionGate(), menus=(menu,))

    def fake_build_action_bindings(**kwargs: object) -> ActionBindings:
        del kwargs
        return bindings

    monkeypatch.setattr(app, "build_action_bindings", fake_build_action_bindings)

    result = app.main(["--no-window", "--frames", "1"])

    assert result == 0
    assert captured["menus"] == (menu,)
    bus = cast(InProcessEventBus, captured["bus"])
    bus.publish(
        GestureDetected(
            timestamp=0.1,
            gesture=GESTURE_POINTING_UP,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.LEFT,
        )
    )
    bus.publish(
        GestureDetected(
            timestamp=0.2,
            gesture=GESTURE_VICTORY,
            confidence=GESTURE_CONFIDENCE,
            handedness=Handedness.RIGHT,
        )
    )

    assert len(menu_action.contexts) == 1
    assert menu_action.contexts[0].gesture is GESTURE_VICTORY
