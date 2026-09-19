"""Tests del anti-intrusos (etapa 11), sin hardware real.

Cubre el dominio de zona/intrusion, la configuracion, los adaptadores de alerta,
el overlay y el runner con camara y detector fakes (bucle real).
"""

import sys
import time
from pathlib import Path
from types import ModuleType
from typing import cast

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray
from pydantic import ValidationError

from recognizer.adapters.alert_sound import SilentAlert, SystemSoundAlert, WinsoundFacade
from recognizer.adapters.ultralytics_detector import UltralyticsDetector
from recognizer.cli import menu
from recognizer.cli.apps import anti_intruder as ai_module
from recognizer.cli.apps.anti_intruder import run_anti_intruder
from recognizer.cli.menu import resolve_runner
from recognizer.core.config import (
    AntiIntruderConfig,
    AppConfig,
    CameraConfig,
    IntrusionAlertConfig,
    IntrusionZoneConfig,
)
from recognizer.core.constants import (
    DEFAULT_INTRUSION_ALERT_REPEAT_SECONDS,
    DEFAULT_INTRUSION_CONFIRM_FRAMES,
    DEFAULT_INTRUSION_RELEASE_FRAMES,
    DEFAULT_INTRUSION_ZONE_X_MAX,
    DEFAULT_INTRUSION_ZONE_X_MIN,
    DEFAULT_INTRUSION_ZONE_Y_MAX,
    DEFAULT_INTRUSION_ZONE_Y_MIN,
    DEFAULT_PEOPLE_CONFIDENCE,
    DEFAULT_PEOPLE_MODEL_PATH,
    PERSON_LABEL,
)
from recognizer.core.domain.app import AppAvailability, AppCatalog, AppId, AppRunRequest
from recognizer.core.domain.detection import BoundingBox, Detection
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.intrusion import IntrusionZone
from recognizer.core.domain.tracking import TrackedDetection
from recognizer.core.errors import DetectorError
from recognizer.core.ports.alert_sink import AlertSink
from recognizer.core.ports.object_tracker import ObjectTracker

FRAME_SHAPE = (48, 64, 3)


def _bbox(x_min: float, y_min: float, x_max: float, y_max: float) -> BoundingBox:
    return BoundingBox(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)


def _inside_bbox() -> BoundingBox:
    return _bbox(0.4, 0.4, 0.6, 0.6)


def _outside_bbox() -> BoundingBox:
    return _bbox(0.0, 0.0, 0.1, 0.1)


def _tracked(
    track_id: int = 1,
    *,
    bbox: BoundingBox | None = None,
    label: str = PERSON_LABEL,
    confidence: float = 0.9,
) -> TrackedDetection:
    return TrackedDetection(
        track_id=track_id,
        detection=Detection(label=label, confidence=confidence, bbox=bbox or _inside_bbox()),
    )


def _frame() -> Frame:
    data: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    return Frame(data=data, timestamp=1.0)


# --- Configuracion ---


def test_anti_intruder_config_defaults() -> None:
    config = AntiIntruderConfig()

    assert config.model_path == DEFAULT_PEOPLE_MODEL_PATH
    assert config.min_confidence == DEFAULT_PEOPLE_CONFIDENCE
    assert config.target_label == PERSON_LABEL
    assert config.zone.x_min == DEFAULT_INTRUSION_ZONE_X_MIN
    assert config.zone.y_min == DEFAULT_INTRUSION_ZONE_Y_MIN
    assert config.zone.x_max == DEFAULT_INTRUSION_ZONE_X_MAX
    assert config.zone.y_max == DEFAULT_INTRUSION_ZONE_Y_MAX
    assert config.zone.confirm_frames == DEFAULT_INTRUSION_CONFIRM_FRAMES
    assert config.zone.release_frames == DEFAULT_INTRUSION_RELEASE_FRAMES
    assert config.alert.enabled is True
    assert config.alert.repeat_seconds == DEFAULT_INTRUSION_ALERT_REPEAT_SECONDS


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_anti_intruder_config_rejects_bad_confidence(confidence: float) -> None:
    with pytest.raises(ValidationError):
        AntiIntruderConfig(min_confidence=confidence)


def test_anti_intruder_config_rejects_empty_strings() -> None:
    with pytest.raises(ValidationError):
        AntiIntruderConfig(model_path="")
    with pytest.raises(ValidationError):
        AntiIntruderConfig(target_label="")


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_intrusion_zone_config_rejects_out_of_range(value: float) -> None:
    with pytest.raises(ValidationError):
        IntrusionZoneConfig(x_min=value)


def test_intrusion_zone_config_rejects_degenerate_rectangle() -> None:
    with pytest.raises(ValidationError):
        IntrusionZoneConfig(x_min=0.6, x_max=0.4)
    with pytest.raises(ValidationError):
        IntrusionZoneConfig(y_min=0.6, y_max=0.4)


def test_intrusion_alert_config_rejects_negative_repeat() -> None:
    with pytest.raises(ValidationError):
        IntrusionAlertConfig(repeat_seconds=-0.1)


def test_app_config_includes_anti_intruder() -> None:
    config = AppConfig()

    assert config.anti_intruder == AntiIntruderConfig()
    parsed = AppConfig.model_validate(
        {"anti_intruder": {"model_path": "models/x.pt", "min_confidence": 0.7}}
    )
    assert parsed.anti_intruder.model_path == "models/x.pt"
    assert parsed.anti_intruder.min_confidence == 0.7


# --- Adaptadores de alerta ---


class _FakeSoundFacade:
    def __init__(self) -> None:
        self.beeps = 0
        self.stops = 0

    def message_beep(self) -> None:
        self.beeps += 1

    def stop(self) -> None:
        self.stops += 1


def test_system_sound_alert_delegates_to_facade() -> None:
    facade = _FakeSoundFacade()
    sink: AlertSink = SystemSoundAlert(facade=facade)

    sink.notify()
    sink.notify()
    sink.close()

    assert facade.beeps == 2
    assert facade.stops == 1


def test_system_sound_alert_context_manager_closes() -> None:
    facade = _FakeSoundFacade()

    with SystemSoundAlert(facade=facade) as sink:
        sink.notify()

    assert facade.beeps == 1
    assert facade.stops == 1


def test_silent_alert_is_noop() -> None:
    silent = SilentAlert()
    sink: AlertSink = silent

    sink.notify()
    with silent as entered:
        assert entered is silent
    silent.close()


def test_winsound_facade_delegates_to_module(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, ...]] = []
    fake = ModuleType("winsound")
    setattr(fake, "MB_ICONHAND", 16)  # noqa: B010
    setattr(fake, "SND_PURGE", 64)  # noqa: B010
    setattr(fake, "MessageBeep", lambda kind: calls.append(("beep", kind)))  # noqa: B010
    setattr(fake, "PlaySound", lambda sound, flags: calls.append(("stop", sound, flags)))  # noqa: B010
    monkeypatch.setitem(sys.modules, "winsound", fake)

    facade = WinsoundFacade()
    facade.message_beep()
    facade.stop()

    assert calls == [("beep", 16), ("stop", None, 64)]


def test_winsound_facade_without_module_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "winsound", cast("ModuleType", None))

    facade = WinsoundFacade()
    facade.message_beep()
    facade.stop()


# --- Menu y catalogo ---


def test_resolve_anti_intruder_runner_is_lazy() -> None:
    before = set(sys.modules)

    assert resolve_runner(AppId.ANTI_INTRUDER) is run_anti_intruder

    added = set(sys.modules) - before
    assert "ultralytics" not in added
    assert "torch" not in added


def test_anti_intruder_catalog_entry_is_available() -> None:
    catalog = AppCatalog()

    info = catalog.require(AppId.ANTI_INTRUDER)
    assert info.implemented is True
    assert catalog.availability(AppId.ANTI_INTRUDER, enabled={}) is AppAvailability.AVAILABLE
    assert (
        catalog.availability(AppId.ANTI_INTRUDER, enabled={AppId.ANTI_INTRUDER: False})
        is AppAvailability.DISABLED
    )


def test_menu_renders_anti_intruder_as_available() -> None:
    from recognizer.core.config import AppsConfig

    text = menu.render_catalog(AppCatalog(), AppsConfig())

    assert "  3) Anti-intrusos" in text
    assert menu.LABEL_AVAILABLE in text.splitlines()[6]


# --- Runner con dobles (bucle de camara real) ---


class _FakeCamera:
    def __init__(self, config: CameraConfig, frames: list[Frame]) -> None:
        self.config = config
        self._frames = frames
        self.read_calls = 0

    def __enter__(self) -> "_FakeCamera":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def read(self) -> Frame | None:
        self.read_calls += 1
        if self._frames:
            return self._frames.pop(0)
        return None


class _FakeDetectorCM:
    def __init__(
        self,
        config: AntiIntruderConfig,
        script: list[tuple[TrackedDetection, ...]],
    ) -> None:
        self.config = config
        self._script = script
        self.track_calls = 0

    def __enter__(self) -> "_FakeDetectorCM":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def track(self, frame: Frame) -> tuple[TrackedDetection, ...]:
        _ = frame
        self.track_calls += 1
        if self._script:
            return self._script.pop(0)
        return ()


class _FakeAlert:
    def __init__(self) -> None:
        self.notify_calls = 0
        self.close_calls = 0

    def notify(self) -> None:
        self.notify_calls += 1

    def close(self) -> None:
        self.close_calls += 1

    def __enter__(self) -> "_FakeAlert":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


def _patch_runner_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    frames: list[Frame],
    script: list[tuple[TrackedDetection, ...]],
    app_config: AppConfig | None = None,
) -> tuple[_FakeDetectorCM, _FakeAlert, _FakeAlert]:
    resolved = app_config if app_config is not None else AppConfig()
    detector = _FakeDetectorCM(resolved.anti_intruder, script)
    sound = _FakeAlert()
    silent = _FakeAlert()
    camera_holder: list[_FakeCamera] = []

    def camera_factory(config: CameraConfig) -> _FakeCamera:
        camera = _FakeCamera(config, frames)
        camera_holder.append(camera)
        return camera

    monkeypatch.setattr(ai_module, "prepare_workspace", lambda path: path)
    monkeypatch.setattr(ai_module, "load_config", lambda path: resolved)  # noqa: ARG005
    monkeypatch.setattr(
        ai_module,
        "resolve_camera_config",
        lambda *, app_config, device_override: CameraConfig(),  # noqa: ARG005
    )
    monkeypatch.setattr(ai_module, "OpenCVCamera", camera_factory)
    monkeypatch.setattr(ai_module, "UltralyticsDetector", lambda config: detector)  # noqa: ARG005
    monkeypatch.setattr(ai_module, "SystemSoundAlert", lambda: sound)
    monkeypatch.setattr(ai_module, "SilentAlert", lambda: silent)
    monkeypatch.setattr(cv2, "destroyAllWindows", lambda: None)
    return detector, sound, silent


def _app_config_with_zone(
    *,
    enabled: bool,
    confirm_frames: int = 1,
    release_frames: int = 1,
    alert_enabled: bool = True,
    repeat_seconds: float = 0.0,
) -> AppConfig:
    return AppConfig(
        anti_intruder=AntiIntruderConfig(
            zone=IntrusionZoneConfig(
                enabled=enabled,
                confirm_frames=confirm_frames,
                release_frames=release_frames,
            ),
            alert=IntrusionAlertConfig(enabled=alert_enabled, repeat_seconds=repeat_seconds),
        )
    )


def _record_overlay(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[bool, tuple[int, ...], IntrusionZone | None]]:
    calls: list[tuple[bool, tuple[int, ...], IntrusionZone | None]] = []

    def fake_draw(
        image: NDArray[np.uint8],
        *,
        tracked: tuple[TrackedDetection, ...],
        zone: IntrusionZone | None,
        active: bool,
        intruder_ids: frozenset[int],
    ) -> None:
        _ = (image, tracked)
        calls.append((active, tuple(sorted(intruder_ids)), zone))

    monkeypatch.setattr(ai_module, "draw_intrusion_overlay", fake_draw)
    return calls


def test_runner_confirms_intruder_and_notifies_once(monkeypatch: pytest.MonkeyPatch) -> None:
    script: list[tuple[TrackedDetection, ...]] = [(_tracked(1, bbox=_inside_bbox()),)]
    detector, sound, _silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame()],
        script=script,
        app_config=_app_config_with_zone(enabled=True),
    )
    calls = _record_overlay(monkeypatch)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=1)
    assert run_anti_intruder(request) == 0

    assert detector.track_calls == 1
    assert sound.notify_calls == 1
    assert calls[0][0] is True
    assert calls[0][1] == (1,)
    assert calls[0][2] == IntrusionZone(
        x_min=DEFAULT_INTRUSION_ZONE_X_MIN,
        y_min=DEFAULT_INTRUSION_ZONE_Y_MIN,
        x_max=DEFAULT_INTRUSION_ZONE_X_MAX,
        y_max=DEFAULT_INTRUSION_ZONE_Y_MAX,
    )


def test_runner_without_intruder_does_not_notify(monkeypatch: pytest.MonkeyPatch) -> None:
    script: list[tuple[TrackedDetection, ...]] = [(_tracked(1, bbox=_outside_bbox()),)]
    _detector, sound, _silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame()],
        script=script,
        app_config=_app_config_with_zone(enabled=True),
    )
    calls = _record_overlay(monkeypatch)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=1)
    assert run_anti_intruder(request) == 0

    assert sound.notify_calls == 0
    assert calls[0][0] is False
    assert calls[0][1] == ()


def test_runner_repeats_alert_while_active(monkeypatch: pytest.MonkeyPatch) -> None:
    script: list[tuple[TrackedDetection, ...]] = [
        (_tracked(1, bbox=_inside_bbox()),),
        (_tracked(1, bbox=_inside_bbox()),),
        (_tracked(1, bbox=_inside_bbox()),),
    ]
    _detector, sound, _silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame(), _frame(), _frame()],
        script=script,
        app_config=_app_config_with_zone(enabled=True, repeat_seconds=2.0),
    )
    times = iter([100.0, 100.5, 103.0])
    monkeypatch.setattr(time, "monotonic", lambda: next(times))

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=3)
    assert run_anti_intruder(request) == 0

    assert sound.notify_calls == 2


def test_runner_with_zone_disabled_ignores_people(monkeypatch: pytest.MonkeyPatch) -> None:
    script: list[tuple[TrackedDetection, ...]] = [(_tracked(1, bbox=_inside_bbox()),)]
    _detector, sound, _silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame()],
        script=script,
        app_config=_app_config_with_zone(enabled=False),
    )
    calls = _record_overlay(monkeypatch)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=1)
    assert run_anti_intruder(request) == 0

    assert sound.notify_calls == 0
    assert calls[0][0] is False
    assert calls[0][1] == ()
    assert calls[0][2] is None


def test_runner_with_alert_disabled_uses_silent_alert(monkeypatch: pytest.MonkeyPatch) -> None:
    script: list[tuple[TrackedDetection, ...]] = [(_tracked(1, bbox=_inside_bbox()),)]
    _detector, sound, silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame()],
        script=script,
        app_config=_app_config_with_zone(enabled=True, alert_enabled=False),
    )

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=1)
    assert run_anti_intruder(request) == 0

    assert sound.notify_calls == 0
    assert silent.close_calls >= 1


def test_runner_stops_on_quit_key_and_returns_to_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script: list[tuple[TrackedDetection, ...]] = [
        (_tracked(1, bbox=_inside_bbox()),),
        (_tracked(1, bbox=_inside_bbox()),),
        (_tracked(1, bbox=_inside_bbox()),),
    ]
    detector, _sound, _silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame(), _frame(), _frame()],
        script=script,
        app_config=_app_config_with_zone(enabled=True),
    )
    keys = iter([0, ord("q")])
    shown: list[str] = []
    monkeypatch.setattr(cv2, "imshow", lambda name, _data: shown.append(name))
    monkeypatch.setattr(cv2, "waitKey", lambda _delay: next(keys))

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=True, max_frames=0)
    assert run_anti_intruder(request) == 0

    assert detector.track_calls == 2
    assert shown == [ai_module.WINDOW_NAME, ai_module.WINDOW_NAME]


def test_runner_rejects_headless_without_frames() -> None:
    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=0)

    assert run_anti_intruder(request) == 1


def test_anti_intruder_detector_config_is_structural() -> None:
    detector: ObjectTracker = UltralyticsDetector(AntiIntruderConfig())

    with pytest.raises(DetectorError, match="no esta abierto"):
        detector.track(_frame())
