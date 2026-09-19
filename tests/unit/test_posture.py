"""Tests de la app Postura ergonomica (etapa 12): config y runner con dobles.

El runner se prueba con camara, estimador y alerta fake sobre el bucle real de
camara; no se abre hardware ni se importan ultralytics/torch.
"""

import sys
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray
from pydantic import ValidationError

from recognizer.cli import menu
from recognizer.cli.apps import posture as posture_module
from recognizer.cli.apps.posture import run_posture
from recognizer.cli.menu import resolve_runner
from recognizer.core.config import (
    AppConfig,
    CameraConfig,
    PostureAlertConfig,
    PostureConfig,
    PostureTolerancesConfig,
)
from recognizer.core.constants import (
    DEFAULT_PEOPLE_CONFIDENCE,
    DEFAULT_POSTURE_CALIBRATION_FRAMES,
    DEFAULT_POSTURE_CONFIRM_FRAMES,
    DEFAULT_POSTURE_KEYPOINT_CONFIDENCE,
    DEFAULT_POSTURE_MAX_HEAD_OFFSET_RATIO,
    DEFAULT_POSTURE_MAX_SHOULDER_TILT_RATIO,
    DEFAULT_POSTURE_MAX_TORSO_ANGLE_DEG,
    DEFAULT_POSTURE_MIN_HEAD_HEIGHT_RATIO,
    DEFAULT_POSTURE_MODEL_PATH,
    DEFAULT_POSTURE_RELEASE_FRAMES,
    DEFAULT_POSTURE_TOLERANCE_HEAD_HEIGHT,
    DEFAULT_POSTURE_TOLERANCE_HEAD_OFFSET,
    DEFAULT_POSTURE_TOLERANCE_SHOULDER_TILT,
    DEFAULT_POSTURE_TOLERANCE_TORSO_ANGLE_DEG,
)
from recognizer.core.domain.app import AppAvailability, AppCatalog, AppId, AppRunRequest
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.pose import Keypoint, Pose, PoseKeypoint
from recognizer.core.domain.posture import PostureIssue
from recognizer.settings import load_config

FRAME_SHAPE = (48, 64, 3)
MIN_KEYPOINT_CONFIDENCE = 0.5


# --- Utilidades ---


def _frame() -> Frame:
    data: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    return Frame(data=data, timestamp=1.0)


def _points() -> dict[PoseKeypoint, tuple[float, float]]:
    return {
        PoseKeypoint.NOSE: (0.5, 0.2),
        PoseKeypoint.LEFT_SHOULDER: (0.3, 0.5),
        PoseKeypoint.RIGHT_SHOULDER: (0.7, 0.5),
        PoseKeypoint.LEFT_HIP: (0.35, 0.85),
        PoseKeypoint.RIGHT_HIP: (0.65, 0.85),
    }


def _pose(points: dict[PoseKeypoint, tuple[float, float]]) -> Pose:
    return Pose(
        confidence=0.9,
        keypoints=tuple(
            Keypoint(name=name, x=x, y=y, confidence=0.9) for name, (x, y) in points.items()
        ),
    )


def _good_pose() -> Pose:
    return _pose(_points())


def _bad_pose() -> Pose:
    points = _points()
    points[PoseKeypoint.NOSE] = (0.7, 0.2)
    return _pose(points)


# --- Configuracion ---


def test_posture_config_defaults() -> None:
    config = PostureConfig()

    assert config.model_path == DEFAULT_POSTURE_MODEL_PATH
    assert config.min_confidence == DEFAULT_PEOPLE_CONFIDENCE
    assert config.min_keypoint_confidence == DEFAULT_POSTURE_KEYPOINT_CONFIDENCE
    assert config.calibration_frames == DEFAULT_POSTURE_CALIBRATION_FRAMES
    assert config.tolerances == PostureTolerancesConfig()
    assert config.max_head_offset_ratio == DEFAULT_POSTURE_MAX_HEAD_OFFSET_RATIO
    assert config.min_head_height_ratio == DEFAULT_POSTURE_MIN_HEAD_HEIGHT_RATIO
    assert config.max_torso_angle_deg == DEFAULT_POSTURE_MAX_TORSO_ANGLE_DEG
    assert config.max_shoulder_tilt_ratio == DEFAULT_POSTURE_MAX_SHOULDER_TILT_RATIO
    assert config.confirm_frames == DEFAULT_POSTURE_CONFIRM_FRAMES
    assert config.release_frames == DEFAULT_POSTURE_RELEASE_FRAMES
    assert config.alert == PostureAlertConfig()


def test_posture_tolerances_config_defaults() -> None:
    tolerances = PostureTolerancesConfig()

    assert tolerances.head_offset == DEFAULT_POSTURE_TOLERANCE_HEAD_OFFSET
    assert tolerances.head_height == DEFAULT_POSTURE_TOLERANCE_HEAD_HEIGHT
    assert tolerances.torso_angle_deg == DEFAULT_POSTURE_TOLERANCE_TORSO_ANGLE_DEG
    assert tolerances.shoulder_tilt == DEFAULT_POSTURE_TOLERANCE_SHOULDER_TILT


@pytest.mark.parametrize(
    "field",
    ["head_offset", "head_height", "torso_angle_deg", "shoulder_tilt"],
)
def test_posture_tolerances_config_rejects_negative(field: str) -> None:
    with pytest.raises(ValidationError):
        PostureTolerancesConfig.model_validate({field: -0.1})


def test_posture_tolerances_config_rejects_torso_angle_out_of_range() -> None:
    with pytest.raises(ValidationError):
        PostureTolerancesConfig.model_validate({"torso_angle_deg": 180.1})


@pytest.mark.parametrize("value", [-1, -10])
def test_posture_config_rejects_negative_calibration_frames(value: int) -> None:
    with pytest.raises(ValidationError):
        PostureConfig.model_validate({"calibration_frames": value})


def test_posture_config_parses_from_yaml(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "posture:\n"
        "  calibration_frames: 12\n"
        "  tolerances:\n"
        "    head_offset: 0.2\n"
        "    head_height: 0.25\n"
        "    torso_angle_deg: 10.0\n"
        "    shoulder_tilt: 0.05\n",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.posture.calibration_frames == 12
    assert config.posture.tolerances.head_offset == 0.2
    assert config.posture.tolerances.head_height == 0.25
    assert config.posture.tolerances.torso_angle_deg == 10.0
    assert config.posture.tolerances.shoulder_tilt == 0.05


@pytest.mark.parametrize("field", ["min_confidence", "min_keypoint_confidence"])
@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_posture_config_rejects_bad_confidence(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        PostureConfig.model_validate({field: value})


@pytest.mark.parametrize("field", ["max_head_offset_ratio", "max_shoulder_tilt_ratio"])
@pytest.mark.parametrize("value", [0.0, -0.1])
def test_posture_config_rejects_non_positive_ratios(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        PostureConfig.model_validate({field: value})


def test_posture_config_rejects_negative_head_height_ratio() -> None:
    with pytest.raises(ValidationError):
        PostureConfig.model_validate({"min_head_height_ratio": -0.1})


@pytest.mark.parametrize("value", [-0.1, 180.1])
def test_posture_config_rejects_torso_angle_out_of_range(value: float) -> None:
    with pytest.raises(ValidationError):
        PostureConfig.model_validate({"max_torso_angle_deg": value})


@pytest.mark.parametrize("field", ["confirm_frames", "release_frames"])
def test_posture_config_rejects_zero_counters(field: str) -> None:
    with pytest.raises(ValidationError):
        PostureConfig.model_validate({field: 0})


def test_posture_config_rejects_empty_model_path() -> None:
    with pytest.raises(ValidationError):
        PostureConfig(model_path="")


def test_posture_alert_config_rejects_negative_repeat() -> None:
    with pytest.raises(ValidationError):
        PostureAlertConfig(repeat_seconds=-0.1)


def test_app_config_includes_posture() -> None:
    config = AppConfig()

    assert config.posture == PostureConfig()
    parsed = AppConfig.model_validate(
        {"posture": {"model_path": "models/x.pt", "confirm_frames": 3}}
    )
    assert parsed.posture.model_path == "models/x.pt"
    assert parsed.posture.confirm_frames == 3


# --- Menu y catalogo ---


def test_resolve_posture_runner_is_lazy() -> None:
    before = set(sys.modules)

    assert resolve_runner(AppId.POSTURE) is run_posture

    added = set(sys.modules) - before
    assert "ultralytics" not in added
    assert "torch" not in added


def test_posture_catalog_entry_is_available() -> None:
    catalog = AppCatalog()

    info = catalog.require(AppId.POSTURE)
    assert info.implemented is True
    assert catalog.availability(AppId.POSTURE, enabled={}) is AppAvailability.AVAILABLE
    assert (
        catalog.availability(AppId.POSTURE, enabled={AppId.POSTURE: False})
        is AppAvailability.DISABLED
    )


def test_menu_renders_posture_as_available() -> None:
    from recognizer.core.config import AppsConfig

    text = menu.render_catalog(AppCatalog(), AppsConfig())

    assert "  4) Postura ergonomica" in text
    assert menu.LABEL_AVAILABLE in text.splitlines()[7]


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
    def __init__(self, config: PostureConfig, script: list[tuple[Pose, ...]]) -> None:
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
    estimator = _FakeEstimatorCM(resolved.posture, script)
    sound = _FakeAlert()
    silent = _FakeAlert()
    camera_holder: list[_FakeCamera] = []

    def camera_factory(config: CameraConfig) -> _FakeCamera:
        camera = _FakeCamera(config, frames)
        camera_holder.append(camera)
        return camera

    monkeypatch.setattr(posture_module, "prepare_workspace", lambda path: path)
    monkeypatch.setattr(posture_module, "load_config", lambda path: resolved)  # noqa: ARG005
    monkeypatch.setattr(
        posture_module,
        "resolve_camera_config",
        lambda *, app_config, device_override: CameraConfig(),  # noqa: ARG005
    )
    monkeypatch.setattr(posture_module, "OpenCVCamera", camera_factory)
    monkeypatch.setattr(
        posture_module,
        "UltralyticsPoseEstimator",
        lambda config: estimator,  # noqa: ARG005
    )
    monkeypatch.setattr(posture_module, "SystemSoundAlert", lambda: sound)
    monkeypatch.setattr(posture_module, "SilentAlert", lambda: silent)
    monkeypatch.setattr(cv2, "destroyAllWindows", lambda: None)
    return estimator, sound, silent


def _app_config(
    *,
    alert_enabled: bool = True,
    repeat_seconds: float = 0.0,
    confirm_frames: int = 1,
    release_frames: int = 1,
    calibration_frames: int = 0,
) -> AppConfig:
    return AppConfig(
        posture=PostureConfig(
            confirm_frames=confirm_frames,
            release_frames=release_frames,
            calibration_frames=calibration_frames,
            alert=PostureAlertConfig(enabled=alert_enabled, repeat_seconds=repeat_seconds),
        )
    )


@dataclass(frozen=True)
class _OverlayCall:
    active: bool
    issues: tuple[PostureIssue, ...]
    calibrating: bool


def _record_overlay(monkeypatch: pytest.MonkeyPatch) -> list[_OverlayCall]:
    calls: list[_OverlayCall] = []

    def fake_draw(
        image: NDArray[np.uint8],
        *,
        poses: tuple[Pose, ...],
        active: bool,
        issues: tuple[PostureIssue, ...],
        min_keypoint_confidence: float,
        calibrating: bool = False,
    ) -> None:
        _ = (image, poses, min_keypoint_confidence)
        calls.append(_OverlayCall(active=active, issues=issues, calibrating=calibrating))

    monkeypatch.setattr(posture_module, "draw_posture_overlay", fake_draw)
    return calls


def test_runner_rejects_headless_without_frames() -> None:
    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=0)

    assert run_posture(request) == 1


def test_runner_confirms_bad_posture_and_notifies(monkeypatch: pytest.MonkeyPatch) -> None:
    estimator, sound, _silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame()],
        script=[(_bad_pose(),)],
        app_config=_app_config(),
    )
    calls = _record_overlay(monkeypatch)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=1)
    assert run_posture(request) == 0

    assert estimator.estimate_calls == 1
    assert sound.notify_calls == 1
    assert calls[0].active is True
    assert calls[0].issues == (PostureIssue.HEAD_FORWARD,)
    assert calls[0].calibrating is False


def test_runner_good_posture_does_not_notify(monkeypatch: pytest.MonkeyPatch) -> None:
    estimator, sound, _silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame()],
        script=[(_good_pose(),)],
        app_config=_app_config(),
    )
    calls = _record_overlay(monkeypatch)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=1)
    assert run_posture(request) == 0

    assert estimator.estimate_calls == 1
    assert sound.notify_calls == 0
    assert calls[0] == _OverlayCall(active=False, issues=(), calibrating=False)


def test_runner_does_not_alert_while_calibrating(monkeypatch: pytest.MonkeyPatch) -> None:
    _estimator, sound, _silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame(), _frame()],
        script=[(_bad_pose(),), (_bad_pose(),)],
        app_config=_app_config(calibration_frames=2),
    )
    calls = _record_overlay(monkeypatch)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=2)
    assert run_posture(request) == 0

    assert sound.notify_calls == 0
    assert len(calls) == 2
    assert all(call.calibrating is True for call in calls)
    assert all(call.active is False for call in calls)


def test_runner_alerts_after_calibration_on_deviation(monkeypatch: pytest.MonkeyPatch) -> None:
    _estimator, sound, _silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame(), _frame()],
        script=[(_good_pose(),), (_bad_pose(),)],
        app_config=_app_config(calibration_frames=1),
    )
    calls = _record_overlay(monkeypatch)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=2)
    assert run_posture(request) == 0

    assert sound.notify_calls == 1
    assert calls[0].calibrating is True
    assert calls[1].calibrating is False
    assert calls[1].active is True
    assert calls[1].issues == (PostureIssue.HEAD_FORWARD,)


def test_runner_repeats_alert_while_active(monkeypatch: pytest.MonkeyPatch) -> None:
    _estimator, sound, _silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame(), _frame(), _frame()],
        script=[(_bad_pose(),), (_bad_pose(),), (_bad_pose(),)],
        app_config=_app_config(repeat_seconds=2.0),
    )
    times = iter([100.0, 100.5, 103.0])
    monkeypatch.setattr(time, "monotonic", lambda: next(times))

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=3)
    assert run_posture(request) == 0

    assert sound.notify_calls == 2


def test_runner_with_alert_disabled_uses_silent_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _estimator, sound, silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame()],
        script=[(_bad_pose(),)],
        app_config=_app_config(alert_enabled=False),
    )

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=1)
    assert run_posture(request) == 0

    assert sound.notify_calls == 0
    assert silent.close_calls >= 1


def test_runner_stops_on_quit_key_and_returns_to_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    estimator, _sound, _silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame(), _frame(), _frame()],
        script=[(_good_pose(),), (_good_pose(),), (_good_pose(),)],
        app_config=_app_config(),
    )
    keys = iter([0, ord("q")])
    shown: list[str] = []
    monkeypatch.setattr(cv2, "imshow", lambda name, _data: shown.append(name))
    monkeypatch.setattr(cv2, "waitKey", lambda _delay: next(keys))

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=True, max_frames=0)
    assert run_posture(request) == 0

    assert estimator.estimate_calls == 2
    assert shown == [posture_module.WINDOW_NAME, posture_module.WINDOW_NAME]
