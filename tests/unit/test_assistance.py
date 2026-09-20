"""Tests de la app Manos arriba / asistencia (etapa 16): dominio, config y runner.

El runner se prueba con camara, estimador y alerta fake sobre el bucle real de
camara; no se abre hardware ni se importan ultralytics/torch.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray
from pydantic import ValidationError

from recognizer.cli import menu
from recognizer.cli.apps import assistance as assistance_module
from recognizer.cli.apps.assistance import run_assistance
from recognizer.cli.menu import resolve_runner
from recognizer.core.config import (
    AppConfig,
    AssistanceAlertConfig,
    AssistanceConfig,
    CameraConfig,
)
from recognizer.core.constants import (
    DEFAULT_ASSISTANCE_CONFIRM_FRAMES,
    DEFAULT_ASSISTANCE_KEYPOINT_CONFIDENCE,
    DEFAULT_ASSISTANCE_MODEL_PATH,
    DEFAULT_ASSISTANCE_RAISE_MARGIN,
    DEFAULT_ASSISTANCE_RELEASE_FRAMES,
    DEFAULT_ASSISTANCE_REQUIRED_ARMS,
    DEFAULT_PEOPLE_CONFIDENCE,
)
from recognizer.core.domain.app import AppAvailability, AppCatalog, AppId, AppRunRequest
from recognizer.core.domain.assistance import AssistanceMonitor, raised_arms
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.pose import Keypoint, Pose, PoseKeypoint
from recognizer.core.errors import ConfigError

FRAME_SHAPE = (48, 64, 3)
MIN_KEYPOINT_CONFIDENCE = 0.5
RAISE_MARGIN = 0.05
SHOULDER_Y = 0.5
WRIST_UP_Y = 0.3
WRIST_DOWN_Y = 0.7


# --- Utilidades ---


def _frame() -> Frame:
    data: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    return Frame(data=data, timestamp=1.0)


def _points(
    *,
    left_wrist: tuple[float, float] = (0.3, WRIST_DOWN_Y),
    right_wrist: tuple[float, float] = (0.7, WRIST_DOWN_Y),
) -> dict[PoseKeypoint, tuple[float, float]]:
    return {
        PoseKeypoint.LEFT_SHOULDER: (0.3, SHOULDER_Y),
        PoseKeypoint.RIGHT_SHOULDER: (0.7, SHOULDER_Y),
        PoseKeypoint.LEFT_ELBOW: (0.25, 0.6),
        PoseKeypoint.RIGHT_ELBOW: (0.75, 0.6),
        PoseKeypoint.LEFT_WRIST: left_wrist,
        PoseKeypoint.RIGHT_WRIST: right_wrist,
    }


def _pose(points: dict[PoseKeypoint, tuple[float, float]]) -> Pose:
    return Pose(
        confidence=0.9,
        keypoints=tuple(
            Keypoint(name=name, x=x, y=y, confidence=0.9) for name, (x, y) in points.items()
        ),
    )


def _arms_down_pose() -> Pose:
    return _pose(_points())


def _one_arm_pose() -> Pose:
    return _pose(_points(left_wrist=(0.3, WRIST_UP_Y)))


def _arms_up_pose() -> Pose:
    return _pose(_points(left_wrist=(0.3, WRIST_UP_Y), right_wrist=(0.7, WRIST_UP_Y)))


# --- Dominio: conteo de brazos ---


def test_raised_arms_counts_both_up() -> None:
    assert (
        raised_arms(
            _arms_up_pose(),
            min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE,
            raise_margin=RAISE_MARGIN,
        )
        == 2
    )


def test_raised_arms_counts_single_up() -> None:
    assert (
        raised_arms(
            _one_arm_pose(),
            min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE,
            raise_margin=RAISE_MARGIN,
        )
        == 1
    )


def test_raised_arms_counts_none_down() -> None:
    assert (
        raised_arms(
            _arms_down_pose(),
            min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE,
            raise_margin=RAISE_MARGIN,
        )
        == 0
    )


def test_raised_arms_respects_margin() -> None:
    points = _points(left_wrist=(0.3, SHOULDER_Y - RAISE_MARGIN / 2))

    assert (
        raised_arms(
            _pose(points),
            min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE,
            raise_margin=RAISE_MARGIN,
        )
        == 0
    )


def test_raised_arms_ignores_low_confidence_wrist() -> None:
    pose = Pose(
        confidence=0.9,
        keypoints=(
            Keypoint(name=PoseKeypoint.LEFT_SHOULDER, x=0.3, y=SHOULDER_Y, confidence=0.9),
            Keypoint(name=PoseKeypoint.LEFT_WRIST, x=0.3, y=WRIST_UP_Y, confidence=0.1),
        ),
    )

    assert (
        raised_arms(
            pose,
            min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE,
            raise_margin=RAISE_MARGIN,
        )
        == 0
    )


def test_raised_arms_ignores_missing_shoulder() -> None:
    pose = Pose(
        confidence=0.9,
        keypoints=(Keypoint(name=PoseKeypoint.LEFT_WRIST, x=0.3, y=WRIST_UP_Y, confidence=0.9),),
    )

    assert (
        raised_arms(
            pose,
            min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE,
            raise_margin=RAISE_MARGIN,
        )
        == 0
    )


# --- Dominio: monitor con debounce ---


def _monitor(**overrides: object) -> AssistanceMonitor:
    params: dict[str, object] = {
        "min_keypoint_confidence": MIN_KEYPOINT_CONFIDENCE,
        "raise_margin": RAISE_MARGIN,
        "required_arms": 2,
        "confirm_frames": 2,
        "release_frames": 2,
    }
    params.update(overrides)
    return AssistanceMonitor(**params)  # type: ignore[arg-type]


def test_monitor_confirms_after_consecutive_up_frames() -> None:
    monitor = _monitor()

    first = monitor.update((_arms_up_pose(),))
    second = monitor.update((_arms_up_pose(),))

    assert first.active is False
    assert second.active is True
    assert second.raised == (0,)
    assert second.people == 1


def test_monitor_releases_after_down_frames() -> None:
    monitor = _monitor()
    monitor.update((_arms_up_pose(),))
    monitor.update((_arms_up_pose(),))

    monitor.update((_arms_down_pose(),))
    snapshot = monitor.update((_arms_down_pose(),))

    assert snapshot.active is False
    assert snapshot.raised == ()


def test_monitor_requires_both_arms_by_default() -> None:
    monitor = _monitor()

    snapshot = monitor.update((_one_arm_pose(),))

    assert snapshot.active is False
    assert snapshot.raised == ()


def test_monitor_single_arm_mode_confirms() -> None:
    monitor = _monitor(required_arms=1, confirm_frames=1)

    snapshot = monitor.update((_one_arm_pose(),))

    assert snapshot.active is True
    assert snapshot.raised == (0,)


def test_monitor_tracks_raised_indices() -> None:
    monitor = _monitor(required_arms=1, confirm_frames=1)

    snapshot = monitor.update((_arms_down_pose(), _arms_up_pose()))

    assert snapshot.raised == (1,)
    assert snapshot.people == 2


def test_monitor_empty_frame_counts_as_down() -> None:
    monitor = _monitor(confirm_frames=1, release_frames=1)
    monitor.update((_arms_up_pose(),))

    snapshot = monitor.update(())

    assert snapshot.active is False


def test_monitor_reset_clears_state() -> None:
    monitor = _monitor(confirm_frames=1)
    monitor.update((_arms_up_pose(),))
    monitor.reset()

    snapshot = monitor.update((_arms_down_pose(),))

    assert snapshot.active is False


def test_monitor_rejects_invalid_required_arms() -> None:
    with pytest.raises(ConfigError, match="required_arms"):
        _monitor(required_arms=3)


def test_monitor_rejects_negative_margin() -> None:
    with pytest.raises(ConfigError, match="raise_margin"):
        _monitor(raise_margin=-0.1)


def test_monitor_rejects_invalid_frames() -> None:
    with pytest.raises(ConfigError, match="confirm_frames"):
        _monitor(confirm_frames=0)
    with pytest.raises(ConfigError, match="release_frames"):
        _monitor(release_frames=0)


# --- Configuracion ---


def test_assistance_config_defaults() -> None:
    config = AssistanceConfig()

    assert config.model_path == DEFAULT_ASSISTANCE_MODEL_PATH
    assert config.min_confidence == DEFAULT_PEOPLE_CONFIDENCE
    assert config.min_keypoint_confidence == DEFAULT_ASSISTANCE_KEYPOINT_CONFIDENCE
    assert config.raise_margin == DEFAULT_ASSISTANCE_RAISE_MARGIN
    assert config.required_arms == DEFAULT_ASSISTANCE_REQUIRED_ARMS
    assert config.confirm_frames == DEFAULT_ASSISTANCE_CONFIRM_FRAMES
    assert config.release_frames == DEFAULT_ASSISTANCE_RELEASE_FRAMES
    assert config.alert == AssistanceAlertConfig()


def test_assistance_config_rejects_invalid_values() -> None:
    with pytest.raises(ValidationError):
        AssistanceConfig(required_arms=0)
    with pytest.raises(ValidationError):
        AssistanceConfig(required_arms=3)
    with pytest.raises(ValidationError):
        AssistanceConfig(raise_margin=-0.1)
    with pytest.raises(ValidationError):
        AssistanceAlertConfig(repeat_seconds=-0.1)


def test_app_config_includes_assistance() -> None:
    config = AppConfig()

    assert config.assistance == AssistanceConfig()
    parsed = AppConfig.model_validate({"assistance": {"required_arms": 1, "confirm_frames": 3}})
    assert parsed.assistance.required_arms == 1
    assert parsed.assistance.confirm_frames == 3


def test_assistance_config_loads_from_yaml(tmp_path: Path) -> None:
    from recognizer.settings import load_config

    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "assistance:\n  required_arms: 1\n  raise_margin: 0.1\n  alert:\n    repeat_seconds: 0\n",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.assistance.required_arms == 1
    assert config.assistance.raise_margin == 0.1
    assert config.assistance.alert.repeat_seconds == 0


# --- Menu y catalogo ---


def test_resolve_assistance_runner_is_lazy() -> None:
    before = set(sys.modules)

    assert resolve_runner(AppId.ASSISTANCE) is run_assistance

    added = set(sys.modules) - before
    assert "ultralytics" not in added
    assert "torch" not in added


def test_assistance_catalog_entry_is_available() -> None:
    catalog = AppCatalog()

    info = catalog.require(AppId.ASSISTANCE)
    assert info.implemented is True
    assert catalog.availability(AppId.ASSISTANCE, enabled={}) is AppAvailability.AVAILABLE
    assert (
        catalog.availability(AppId.ASSISTANCE, enabled={AppId.ASSISTANCE: False})
        is AppAvailability.DISABLED
    )


def test_menu_renders_assistance_as_available() -> None:
    from recognizer.core.config import AppsConfig

    text = menu.render_catalog(AppCatalog(), AppsConfig())

    assert "  6) Manos arriba / asistencia" in text
    assert menu.LABEL_AVAILABLE in text.splitlines()[9]


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


class _FakeEstimatorCM:
    def __init__(self, config: AssistanceConfig, script: list[tuple[Pose, ...]]) -> None:
        self.config = config
        self._script = script
        self.estimate_calls = 0

    def __enter__(self) -> "_FakeEstimatorCM":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def estimate(self, frame: Frame) -> tuple[Pose, ...]:
        _ = frame
        self.estimate_calls += 1
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
    script: list[tuple[Pose, ...]],
    app_config: AppConfig | None = None,
) -> tuple[_FakeEstimatorCM, _FakeAlert, _FakeAlert]:
    resolved = app_config if app_config is not None else AppConfig()
    estimator = _FakeEstimatorCM(resolved.assistance, script)
    sound = _FakeAlert()
    silent = _FakeAlert()
    camera_holder: list[_FakeCamera] = []

    def camera_factory(config: CameraConfig) -> _FakeCamera:
        camera = _FakeCamera(config, frames)
        camera_holder.append(camera)
        return camera

    monkeypatch.setattr(assistance_module, "prepare_workspace", lambda path: path)
    monkeypatch.setattr(assistance_module, "load_config", lambda path: resolved)  # noqa: ARG005
    monkeypatch.setattr(
        assistance_module,
        "resolve_camera_config",
        lambda *, app_config, device_override: CameraConfig(),  # noqa: ARG005
    )
    monkeypatch.setattr(assistance_module, "OpenCVCamera", camera_factory)
    monkeypatch.setattr(
        assistance_module,
        "UltralyticsPoseEstimator",
        lambda config: estimator,  # noqa: ARG005
    )
    monkeypatch.setattr(assistance_module, "SystemSoundAlert", lambda: sound)
    monkeypatch.setattr(assistance_module, "SilentAlert", lambda: silent)
    monkeypatch.setattr(cv2, "destroyAllWindows", lambda: None)
    return estimator, sound, silent


def _app_config(
    *,
    alert_enabled: bool = True,
    repeat_seconds: float = 0.0,
    confirm_frames: int = 1,
    release_frames: int = 1,
    required_arms: int = 2,
) -> AppConfig:
    return AppConfig(
        assistance=AssistanceConfig(
            confirm_frames=confirm_frames,
            release_frames=release_frames,
            required_arms=required_arms,
            alert=AssistanceAlertConfig(enabled=alert_enabled, repeat_seconds=repeat_seconds),
        )
    )


@dataclass(frozen=True)
class _OverlayCall:
    active: bool
    raised: tuple[int, ...]


def _record_overlay(monkeypatch: pytest.MonkeyPatch) -> list[_OverlayCall]:
    calls: list[_OverlayCall] = []

    def fake_draw(
        image: NDArray[np.uint8],
        *,
        poses: tuple[Pose, ...],
        active: bool,
        raised: tuple[int, ...],
        min_keypoint_confidence: float,
        raise_margin: float,
    ) -> None:
        _ = (image, poses, min_keypoint_confidence, raise_margin)
        calls.append(_OverlayCall(active=active, raised=raised))

    monkeypatch.setattr(assistance_module, "draw_assistance_overlay", fake_draw)
    return calls


def test_runner_rejects_headless_without_frames() -> None:
    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=0)

    assert run_assistance(request) == 1


def test_runner_confirms_arms_up_and_notifies(monkeypatch: pytest.MonkeyPatch) -> None:
    estimator, sound, _silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame()],
        script=[(_arms_up_pose(),)],
        app_config=_app_config(),
    )
    calls = _record_overlay(monkeypatch)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=1)
    assert run_assistance(request) == 0

    assert estimator.estimate_calls == 1
    assert sound.notify_calls == 1
    assert calls[0] == _OverlayCall(active=True, raised=(0,))


def test_runner_arms_down_does_not_notify(monkeypatch: pytest.MonkeyPatch) -> None:
    estimator, sound, _silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame()],
        script=[(_arms_down_pose(),)],
        app_config=_app_config(),
    )
    calls = _record_overlay(monkeypatch)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=1)
    assert run_assistance(request) == 0

    assert estimator.estimate_calls == 1
    assert sound.notify_calls == 0
    assert calls[0] == _OverlayCall(active=False, raised=())


def test_runner_repeats_alert_while_active(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    _estimator, sound, _silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame(), _frame(), _frame()],
        script=[(_arms_up_pose(),), (_arms_up_pose(),), (_arms_up_pose(),)],
        app_config=_app_config(repeat_seconds=2.0),
    )
    times = iter([100.0, 100.5, 103.0])
    monkeypatch.setattr(time, "monotonic", lambda: next(times))

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=3)
    assert run_assistance(request) == 0

    assert sound.notify_calls == 2


def test_runner_with_alert_disabled_uses_silent_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _estimator, sound, silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame()],
        script=[(_arms_up_pose(),)],
        app_config=_app_config(alert_enabled=False),
    )

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=1)
    assert run_assistance(request) == 0

    assert sound.notify_calls == 0
    assert silent.close_calls >= 1


def test_runner_stops_on_quit_key_and_returns_to_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    estimator, _sound, _silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame(), _frame(), _frame()],
        script=[(_arms_down_pose(),), (_arms_down_pose(),), (_arms_down_pose(),)],
        app_config=_app_config(),
    )
    keys = iter([0, ord("q")])
    shown: list[str] = []
    monkeypatch.setattr(cv2, "imshow", lambda name, _data: shown.append(name))
    monkeypatch.setattr(cv2, "waitKey", lambda _delay: next(keys))

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=True, max_frames=0)
    assert run_assistance(request) == 0

    assert estimator.estimate_calls == 2
    assert shown == [assistance_module.WINDOW_NAME, assistance_module.WINDOW_NAME]
