"""Tests de la app Detector de caidas (etapa 20): dominio, config y runner.

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
from recognizer.cli.apps import fall_detector as fall_module
from recognizer.cli.apps.fall_detector import run_fall_detector
from recognizer.cli.menu import resolve_runner
from recognizer.core.config import (
    AppConfig,
    CameraConfig,
    FallDetectorAlertConfig,
    FallDetectorConfig,
)
from recognizer.core.constants import (
    DEFAULT_FALL_ASPECT_RATIO,
    DEFAULT_FALL_CENTER_Y,
    DEFAULT_FALL_CONFIRM_FRAMES,
    DEFAULT_FALL_KEYPOINT_CONFIDENCE,
    DEFAULT_FALL_MIN_CONFIDENCE,
    DEFAULT_FALL_MODEL_PATH,
    DEFAULT_FALL_RELEASE_FRAMES,
    DEFAULT_FALL_STILLNESS_THRESHOLD,
    DEFAULT_FALL_STILLNESS_WINDOW,
)
from recognizer.core.domain.app import AppAvailability, AppCatalog, AppId, AppRunRequest
from recognizer.core.domain.fall import FallDetector, measure_fall
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.pose import Keypoint, Pose, PoseKeypoint
from recognizer.core.errors import ConfigError

FRAME_SHAPE = (48, 64, 3)
MIN_KEYPOINT_CONFIDENCE = 0.5

# Postura de pie: torso vertical, centro arriba.
STANDING_SHOULDER_Y = 0.1
STANDING_HIP_Y = 0.6
STANDING_LEFT_X = 0.4
STANDING_RIGHT_X = 0.6

# Postura caida: torso horizontal, centro abajo.
FALLEN_SHOULDER_Y = 0.7
FALLEN_HIP_Y = 0.75
FALLEN_LEFT_X = 0.1
FALLEN_RIGHT_X = 0.9


# --- Utilidades ---


def _frame() -> Frame:
    data: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    return Frame(data=data, timestamp=1.0)


def _standing_pose() -> Pose:
    """Postura de pie: torso vertical, centro arriba."""
    return Pose(
        confidence=0.9,
        keypoints=(
            Keypoint(
                name=PoseKeypoint.LEFT_SHOULDER,
                x=STANDING_LEFT_X,
                y=STANDING_SHOULDER_Y,
                confidence=0.9,
            ),
            Keypoint(
                name=PoseKeypoint.RIGHT_SHOULDER,
                x=STANDING_RIGHT_X,
                y=STANDING_SHOULDER_Y,
                confidence=0.9,
            ),
            Keypoint(
                name=PoseKeypoint.LEFT_HIP,
                x=STANDING_LEFT_X,
                y=STANDING_HIP_Y,
                confidence=0.9,
            ),
            Keypoint(
                name=PoseKeypoint.RIGHT_HIP,
                x=STANDING_RIGHT_X,
                y=STANDING_HIP_Y,
                confidence=0.9,
            ),
        ),
    )


def _fallen_pose() -> Pose:
    """Postura caida: torso horizontal, centro abajo."""
    return Pose(
        confidence=0.9,
        keypoints=(
            Keypoint(
                name=PoseKeypoint.LEFT_SHOULDER,
                x=FALLEN_LEFT_X,
                y=FALLEN_SHOULDER_Y,
                confidence=0.9,
            ),
            Keypoint(
                name=PoseKeypoint.RIGHT_SHOULDER,
                x=FALLEN_RIGHT_X,
                y=FALLEN_SHOULDER_Y,
                confidence=0.9,
            ),
            Keypoint(
                name=PoseKeypoint.LEFT_HIP,
                x=FALLEN_LEFT_X,
                y=FALLEN_HIP_Y,
                confidence=0.9,
            ),
            Keypoint(
                name=PoseKeypoint.RIGHT_HIP,
                x=FALLEN_RIGHT_X,
                y=FALLEN_HIP_Y,
                confidence=0.9,
            ),
        ),
    )


# --- Dominio: measure_fall ---


def test_measure_fall_standing_pose() -> None:
    metrics = measure_fall(_standing_pose(), min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE)
    assert metrics is not None
    assert metrics.aspect_ratio is not None
    assert metrics.center_y is not None
    # Postura de pie: aspecto > 1 (mas alto que ancho), centro arriba.
    assert metrics.aspect_ratio > 1.0
    assert metrics.center_y < 0.5


def test_measure_fall_fallen_pose() -> None:
    metrics = measure_fall(_fallen_pose(), min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE)
    assert metrics is not None
    assert metrics.aspect_ratio is not None
    assert metrics.center_y is not None
    # Postura caida: aspecto < 1 (mas ancho que alto), centro abajo.
    assert metrics.aspect_ratio < 1.0
    assert metrics.center_y > 0.6


def test_measure_fall_insufficient_keypoints() -> None:
    pose = Pose(
        confidence=0.9,
        keypoints=(Keypoint(name=PoseKeypoint.LEFT_SHOULDER, x=0.3, y=0.3, confidence=0.9),),
    )
    metrics = measure_fall(pose, min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE)
    assert metrics is None


def test_measure_fall_ignores_low_confidence() -> None:
    pose = Pose(
        confidence=0.9,
        keypoints=(
            Keypoint(name=PoseKeypoint.LEFT_SHOULDER, x=0.3, y=0.3, confidence=0.1),
            Keypoint(name=PoseKeypoint.RIGHT_SHOULDER, x=0.7, y=0.3, confidence=0.9),
            Keypoint(name=PoseKeypoint.LEFT_HIP, x=0.3, y=0.6, confidence=0.9),
            Keypoint(name=PoseKeypoint.RIGHT_HIP, x=0.7, y=0.6, confidence=0.9),
        ),
    )
    metrics = measure_fall(pose, min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE)
    # Un hombro falta: la caja se calcula con los puntos disponibles.
    assert metrics is not None


def test_measure_fall_with_stillness() -> None:
    metrics = measure_fall(
        _fallen_pose(),
        min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE,
        stillness=0.01,
    )
    assert metrics is not None
    assert metrics.stillness == 0.01


# --- Dominio: FallDetector ---


def _detector(**overrides: object) -> FallDetector:
    params: dict[str, object] = {
        "min_keypoint_confidence": MIN_KEYPOINT_CONFIDENCE,
        "max_aspect_ratio": DEFAULT_FALL_ASPECT_RATIO,
        "min_center_y": DEFAULT_FALL_CENTER_Y,
        "max_stillness": DEFAULT_FALL_STILLNESS_THRESHOLD,
        "stillness_window": DEFAULT_FALL_STILLNESS_WINDOW,
        "confirm_frames": 2,
        "release_frames": 2,
    }
    params.update(overrides)
    return FallDetector(**params)  # type: ignore[arg-type]


def test_detector_confirms_after_consecutive_fallen_frames() -> None:
    detector = _detector()

    first = detector.update((_fallen_pose(),))
    second = detector.update((_fallen_pose(),))
    third = detector.update((_fallen_pose(),))

    assert first.active is False
    assert second.active is False
    assert third.active is True
    assert third.fallen == (0,)
    assert third.people == 1


def test_detector_releases_after_standing_frames() -> None:
    detector = _detector()
    detector.update((_fallen_pose(),))
    detector.update((_fallen_pose(),))

    detector.update((_standing_pose(),))
    snapshot = detector.update((_standing_pose(),))

    assert snapshot.active is False
    assert snapshot.fallen == ()


def test_detector_does_not_fall_when_standing() -> None:
    detector = _detector(confirm_frames=1, release_frames=1)

    snapshot = detector.update((_standing_pose(),))

    assert snapshot.active is False
    assert snapshot.fallen == ()


def test_detector_tracks_fallen_indices() -> None:
    detector = _detector(confirm_frames=1, release_frames=1)

    # First frame initializes stillness history
    detector.update((_standing_pose(), _fallen_pose()))
    # Second frame triggers detection
    snapshot = detector.update((_standing_pose(), _fallen_pose()))

    assert snapshot.fallen == (1,)
    assert snapshot.people == 2


def test_detector_empty_frame_counts_as_standing() -> None:
    detector = _detector(confirm_frames=1, release_frames=1)
    detector.update((_fallen_pose(),))

    snapshot = detector.update(())

    assert snapshot.active is False


def test_detector_reset_clears_state() -> None:
    detector = _detector(confirm_frames=1)
    detector.update((_fallen_pose(),))
    detector.reset()

    snapshot = detector.update((_standing_pose(),))

    assert snapshot.active is False


def test_detector_rejects_invalid_confirm_frames() -> None:
    with pytest.raises(ConfigError, match="confirm_frames"):
        _detector(confirm_frames=0)


def test_detector_rejects_invalid_release_frames() -> None:
    with pytest.raises(ConfigError, match="release_frames"):
        _detector(release_frames=0)


def test_detector_rejects_invalid_stillness_window() -> None:
    with pytest.raises(ConfigError, match="stillness_window"):
        _detector(stillness_window=0)


# --- Configuracion ---


def test_fall_detector_config_defaults() -> None:
    config = FallDetectorConfig()

    assert config.model_path == DEFAULT_FALL_MODEL_PATH
    assert config.min_confidence == DEFAULT_FALL_MIN_CONFIDENCE
    assert config.min_keypoint_confidence == DEFAULT_FALL_KEYPOINT_CONFIDENCE
    assert config.max_aspect_ratio == DEFAULT_FALL_ASPECT_RATIO
    assert config.min_center_y == DEFAULT_FALL_CENTER_Y
    assert config.max_stillness == DEFAULT_FALL_STILLNESS_THRESHOLD
    assert config.stillness_window == DEFAULT_FALL_STILLNESS_WINDOW
    assert config.confirm_frames == DEFAULT_FALL_CONFIRM_FRAMES
    assert config.release_frames == DEFAULT_FALL_RELEASE_FRAMES
    assert config.alert == FallDetectorAlertConfig()


def test_fall_detector_config_rejects_invalid_values() -> None:
    with pytest.raises(ValidationError):
        FallDetectorConfig(confirm_frames=0)
    with pytest.raises(ValidationError):
        FallDetectorConfig(release_frames=0)
    with pytest.raises(ValidationError):
        FallDetectorConfig(max_aspect_ratio=-0.1)
    with pytest.raises(ValidationError):
        FallDetectorAlertConfig(repeat_seconds=-0.1)


def test_app_config_includes_fall_detector() -> None:
    config = AppConfig()

    assert config.fall_detector == FallDetectorConfig()
    parsed = AppConfig.model_validate({"fall_detector": {"max_aspect_ratio": 0.9}})
    assert parsed.fall_detector.max_aspect_ratio == 0.9


def test_fall_detector_config_loads_from_yaml(tmp_path: Path) -> None:
    from recognizer.settings import load_config

    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "fall_detector:\n"
        "  max_aspect_ratio: 0.9\n"
        "  min_center_y: 0.7\n"
        "  alert:\n"
        "    repeat_seconds: 0\n",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.fall_detector.max_aspect_ratio == 0.9
    assert config.fall_detector.min_center_y == 0.7
    assert config.fall_detector.alert.repeat_seconds == 0


# --- Menu y catalogo ---


def test_resolve_fall_detector_runner_is_lazy() -> None:
    before = set(sys.modules)

    assert resolve_runner(AppId.FALL_DETECTOR) is run_fall_detector

    added = set(sys.modules) - before
    assert "ultralytics" not in added
    assert "torch" not in added


def test_fall_detector_catalog_entry_is_available() -> None:
    catalog = AppCatalog()

    info = catalog.require(AppId.FALL_DETECTOR)
    assert info.implemented is True
    assert catalog.availability(AppId.FALL_DETECTOR, enabled={}) is AppAvailability.AVAILABLE
    assert (
        catalog.availability(AppId.FALL_DETECTOR, enabled={AppId.FALL_DETECTOR: False})
        is AppAvailability.DISABLED
    )


def test_menu_renders_fall_detector_as_available() -> None:
    from recognizer.core.config import AppsConfig

    text = menu.render_catalog(AppCatalog(), AppsConfig())

    assert "Detector de caidas" in text
    assert menu.LABEL_AVAILABLE in text


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
    def __init__(self, config: FallDetectorConfig, script: list[tuple[Pose, ...]]) -> None:
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
    estimator = _FakeEstimatorCM(resolved.fall_detector, script)
    sound = _FakeAlert()
    silent = _FakeAlert()
    camera_holder: list[_FakeCamera] = []

    def camera_factory(config: CameraConfig) -> _FakeCamera:
        camera = _FakeCamera(config, frames)
        camera_holder.append(camera)
        return camera

    monkeypatch.setattr(fall_module, "prepare_workspace", lambda path: path)
    monkeypatch.setattr(fall_module, "load_config", lambda path: resolved)  # noqa: ARG005
    monkeypatch.setattr(
        fall_module,
        "resolve_camera_config",
        lambda *, app_config, device_override: CameraConfig(),  # noqa: ARG005
    )
    monkeypatch.setattr(fall_module, "OpenCVCamera", camera_factory)
    monkeypatch.setattr(
        fall_module,
        "UltralyticsPoseEstimator",
        lambda config: estimator,  # noqa: ARG005
    )
    monkeypatch.setattr(fall_module, "SystemSoundAlert", lambda: sound)
    monkeypatch.setattr(fall_module, "SilentAlert", lambda: silent)
    monkeypatch.setattr(cv2, "destroyAllWindows", lambda: None)
    return estimator, sound, silent


def _app_config(
    *,
    alert_enabled: bool = True,
    repeat_seconds: float = 0.0,
    confirm_frames: int = 1,
    release_frames: int = 1,
    stillness_window: int = 10,
) -> AppConfig:
    return AppConfig(
        fall_detector=FallDetectorConfig(
            confirm_frames=confirm_frames,
            release_frames=release_frames,
            stillness_window=stillness_window,
            alert=FallDetectorAlertConfig(enabled=alert_enabled, repeat_seconds=repeat_seconds),
        )
    )


@dataclass(frozen=True)
class _OverlayCall:
    active: bool
    fallen: tuple[int, ...]


def _record_overlay(monkeypatch: pytest.MonkeyPatch) -> list[_OverlayCall]:
    calls: list[_OverlayCall] = []

    def fake_draw(
        image: NDArray[np.uint8],
        *,
        poses: tuple[Pose, ...],
        active: bool,
        fallen: tuple[int, ...],
        min_keypoint_confidence: float,
    ) -> None:
        _ = (image, poses, min_keypoint_confidence)
        calls.append(_OverlayCall(active=active, fallen=fallen))

    monkeypatch.setattr(fall_module, "draw_fall_overlay", fake_draw)
    return calls


def test_runner_rejects_headless_without_frames() -> None:
    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=0)

    assert run_fall_detector(request) == 1


def test_runner_confirms_fallen_and_notifies(monkeypatch: pytest.MonkeyPatch) -> None:
    estimator, sound, _silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame(), _frame()],
        script=[(_fallen_pose(),), (_fallen_pose(),)],
        app_config=_app_config(),
    )
    calls = _record_overlay(monkeypatch)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=2)
    assert run_fall_detector(request) == 0

    assert estimator.estimate_calls == 2
    assert sound.notify_calls == 1
    assert calls[1] == _OverlayCall(active=True, fallen=(0,))


def test_runner_standing_does_not_notify(monkeypatch: pytest.MonkeyPatch) -> None:
    estimator, sound, _silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame()],
        script=[(_standing_pose(),)],
        app_config=_app_config(),
    )
    calls = _record_overlay(monkeypatch)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=1)
    assert run_fall_detector(request) == 0

    assert estimator.estimate_calls == 1
    assert sound.notify_calls == 0
    assert calls[0] == _OverlayCall(active=False, fallen=())


def test_runner_repeats_alert_while_active(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    _estimator, sound, _silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame(), _frame(), _frame()],
        script=[(_fallen_pose(),), (_fallen_pose(),), (_fallen_pose(),)],
        app_config=_app_config(repeat_seconds=2.0),
    )
    times = iter([100.0, 100.5, 103.0])
    monkeypatch.setattr(time, "monotonic", lambda: next(times))

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=3)
    assert run_fall_detector(request) == 0

    assert sound.notify_calls == 2


def test_runner_with_alert_disabled_uses_silent_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _estimator, sound, silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame()],
        script=[(_fallen_pose(),)],
        app_config=_app_config(alert_enabled=False),
    )

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=1)
    assert run_fall_detector(request) == 0

    assert sound.notify_calls == 0
    assert silent.close_calls >= 1
