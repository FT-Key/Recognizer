"""Tests de la app Somnolencia (etapa 22): dominio, config y runner.

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
from recognizer.cli.apps import drowsiness as drowsiness_module
from recognizer.cli.apps.drowsiness import run_drowsiness
from recognizer.cli.menu import resolve_runner
from recognizer.core.config import (
    AppConfig,
    CameraConfig,
    DrowsinessAlertConfig,
    DrowsinessConfig,
)
from recognizer.core.constants import (
    DEFAULT_DROWSINESS_CONFIRM_FRAMES,
    DEFAULT_DROWSINESS_EAR_THRESHOLD,
    DEFAULT_DROWSINESS_EYE_CLOSE_FRAMES,
    DEFAULT_DROWSINESS_HEAD_DROOP_THRESHOLD,
    DEFAULT_DROWSINESS_KEYPOINT_CONFIDENCE,
    DEFAULT_DROWSINESS_MAR_THRESHOLD,
    DEFAULT_DROWSINESS_MIN_CONFIDENCE,
    DEFAULT_DROWSINESS_MODEL_PATH,
    DEFAULT_DROWSINESS_NOD_AMPLITUDE_THRESHOLD,
    DEFAULT_DROWSINESS_NODDING_WINDOW,
    DEFAULT_DROWSINESS_RELEASE_FRAMES,
    DEFAULT_DROWSINESS_YAWN_FRAMES,
)
from recognizer.core.domain.app import AppAvailability, AppCatalog, AppId, AppRunRequest
from recognizer.core.domain.drowsiness import DrowsinessDetector, measure_drowsiness
from recognizer.core.domain.face_landmarks import FaceLandmark3D, FaceMeshResult
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.pose import Keypoint, Pose, PoseKeypoint
from recognizer.core.errors import ConfigError

FRAME_SHAPE = (48, 64, 3)
MIN_KEYPOINT_CONFIDENCE = 0.5

# Postura alerta: cabeza erguida, nariz arriba.
ALERT_NOSE_Y = 0.15
ALERT_SHOULDER_Y = 0.35
ALERT_HIP_Y = 0.60

# Postura somnolienta: cabeza caida, nariz baja.
DROWSY_NOSE_Y = 0.55
DROWSY_SHOULDER_Y = 0.35
DROWSY_HIP_Y = 0.55


# --- Utilidades ---


def _frame() -> Frame:
    data: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    return Frame(data=data, timestamp=1.0)


def _alert_pose() -> Pose:
    """Postura alerta: cabeza erguida, nariz arriba de los hombros."""
    return Pose(
        confidence=0.9,
        keypoints=(
            Keypoint(
                name=PoseKeypoint.NOSE,
                x=0.5,
                y=ALERT_NOSE_Y,
                confidence=0.9,
            ),
            Keypoint(
                name=PoseKeypoint.LEFT_EYE,
                x=0.45,
                y=ALERT_NOSE_Y - 0.05,
                confidence=0.9,
            ),
            Keypoint(
                name=PoseKeypoint.RIGHT_EYE,
                x=0.55,
                y=ALERT_NOSE_Y - 0.05,
                confidence=0.9,
            ),
            Keypoint(
                name=PoseKeypoint.LEFT_EAR,
                x=0.4,
                y=ALERT_NOSE_Y + 0.02,
                confidence=0.9,
            ),
            Keypoint(
                name=PoseKeypoint.RIGHT_EAR,
                x=0.6,
                y=ALERT_NOSE_Y + 0.02,
                confidence=0.9,
            ),
            Keypoint(
                name=PoseKeypoint.LEFT_SHOULDER,
                x=0.35,
                y=ALERT_SHOULDER_Y,
                confidence=0.9,
            ),
            Keypoint(
                name=PoseKeypoint.RIGHT_SHOULDER,
                x=0.65,
                y=ALERT_SHOULDER_Y,
                confidence=0.9,
            ),
            Keypoint(
                name=PoseKeypoint.LEFT_HIP,
                x=0.38,
                y=ALERT_HIP_Y,
                confidence=0.9,
            ),
            Keypoint(
                name=PoseKeypoint.RIGHT_HIP,
                x=0.62,
                y=ALERT_HIP_Y,
                confidence=0.9,
            ),
        ),
    )


def _drowsy_pose() -> Pose:
    """Postura somnolienta: cabeza caida, nariz por debajo de los hombros."""
    return Pose(
        confidence=0.9,
        keypoints=(
            Keypoint(
                name=PoseKeypoint.NOSE,
                x=0.5,
                y=DROWSY_NOSE_Y,
                confidence=0.9,
            ),
            Keypoint(
                name=PoseKeypoint.LEFT_EYE,
                x=0.45,
                y=DROWSY_NOSE_Y - 0.03,
                confidence=0.9,
            ),
            Keypoint(
                name=PoseKeypoint.RIGHT_EYE,
                x=0.55,
                y=DROWSY_NOSE_Y - 0.03,
                confidence=0.9,
            ),
            Keypoint(
                name=PoseKeypoint.LEFT_SHOULDER,
                x=0.35,
                y=DROWSY_SHOULDER_Y,
                confidence=0.9,
            ),
            Keypoint(
                name=PoseKeypoint.RIGHT_SHOULDER,
                x=0.65,
                y=DROWSY_SHOULDER_Y,
                confidence=0.9,
            ),
            Keypoint(
                name=PoseKeypoint.LEFT_HIP,
                x=0.38,
                y=DROWSY_HIP_Y,
                confidence=0.9,
            ),
            Keypoint(
                name=PoseKeypoint.RIGHT_HIP,
                x=0.62,
                y=DROWSY_HIP_Y,
                confidence=0.9,
            ),
        ),
    )


def _make_face_mesh_result(*, ear: float = 0.3, mar: float = 0.02) -> FaceMeshResult:
    """Crea un FaceMeshResult con EAR/MAR especificados."""
    landmarks = tuple(FaceLandmark3D(x=0.5, y=0.5, z=0.0) for _ in range(468))
    return FaceMeshResult(
        landmarks=landmarks,
        ear_left=ear,
        ear_right=ear,
        mar=mar,
    )


# --- Dominio: measure_drowsiness ---


def test_measure_drowsiness_alert_pose() -> None:
    metrics = measure_drowsiness(_alert_pose(), min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE)
    assert metrics is not None
    assert metrics.head_droop is not None
    # Postura alerta: nariz arriba de hombros -> head_droop bajo.
    assert metrics.head_droop < 0.0


def test_measure_drowsiness_drowsy_pose() -> None:
    metrics = measure_drowsiness(_drowsy_pose(), min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE)
    assert metrics is not None
    assert metrics.head_droop is not None
    # Postura somnolienta: nariz abajo de hombros -> head_droop alto.
    assert metrics.head_droop > 0.1


def test_measure_drowsiness_insufficient_keypoints() -> None:
    pose = Pose(
        confidence=0.9,
        keypoints=(Keypoint(name=PoseKeypoint.LEFT_SHOULDER, x=0.3, y=0.3, confidence=0.9),),
    )
    metrics = measure_drowsiness(pose, min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE)
    assert metrics is not None
    assert metrics.head_droop is None


def test_measure_drowsiness_ignores_low_confidence() -> None:
    pose = Pose(
        confidence=0.9,
        keypoints=(
            Keypoint(name=PoseKeypoint.NOSE, x=0.5, y=0.5, confidence=0.1),
            Keypoint(name=PoseKeypoint.LEFT_SHOULDER, x=0.35, y=0.3, confidence=0.9),
            Keypoint(name=PoseKeypoint.RIGHT_SHOULDER, x=0.65, y=0.3, confidence=0.9),
        ),
    )
    metrics = measure_drowsiness(pose, min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE)
    assert metrics is not None
    assert metrics.head_droop is None


def test_measure_drowsiness_with_face_metrics() -> None:
    face = _make_face_mesh_result(ear=0.15, mar=0.6)
    metrics = measure_drowsiness(
        _drowsy_pose(),
        min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE,
        face=face,
    )
    assert metrics is not None
    assert metrics.ear_avg == 0.15
    assert metrics.mar == 0.6


def test_measure_drowsiness_without_face() -> None:
    metrics = measure_drowsiness(
        _drowsy_pose(),
        min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE,
    )
    assert metrics is not None
    assert metrics.ear_avg is None
    assert metrics.mar is None


def test_measure_drowsiness_face_only_without_pose() -> None:
    face = _make_face_mesh_result(ear=0.12, mar=0.65)
    metrics = measure_drowsiness(
        None,
        min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE,
        face=face,
    )
    assert metrics.head_droop is None
    assert metrics.nod_amplitude is None
    assert metrics.ear_avg == 0.12
    assert metrics.mar == 0.65


# --- Dominio: DrowsinessDetector ---


def _detector(**overrides: object) -> DrowsinessDetector:
    params: dict[str, object] = {
        "min_keypoint_confidence": MIN_KEYPOINT_CONFIDENCE,
        "head_droop_threshold": DEFAULT_DROWSINESS_HEAD_DROOP_THRESHOLD,
        "nod_amplitude_threshold": DEFAULT_DROWSINESS_NOD_AMPLITUDE_THRESHOLD,
        "nodding_window": DEFAULT_DROWSINESS_NODDING_WINDOW,
        "ear_threshold": DEFAULT_DROWSINESS_EAR_THRESHOLD,
        "eye_close_frames": DEFAULT_DROWSINESS_EYE_CLOSE_FRAMES,
        "mar_threshold": DEFAULT_DROWSINESS_MAR_THRESHOLD,
        "yawn_frames": DEFAULT_DROWSINESS_YAWN_FRAMES,
        "confirm_frames": 2,
        "release_frames": 2,
    }
    params.update(overrides)
    return DrowsinessDetector(**params)  # type: ignore[arg-type]


def test_detector_confirms_after_consecutive_drowsy_frames() -> None:
    detector = _detector(confirm_frames=4)

    first = detector.update((_drowsy_pose(),))
    second = detector.update((_drowsy_pose(),))
    third = detector.update((_drowsy_pose(),))
    fourth = detector.update((_drowsy_pose(),))

    assert first.active is False
    assert second.active is False
    assert third.active is False
    assert fourth.active is True
    assert fourth.drowsy_count == 1
    assert fourth.people == 1


def test_detector_releases_after_alert_frames() -> None:
    detector = _detector(confirm_frames=2, release_frames=3, nodding_window=3)
    detector.update((_drowsy_pose(),))
    detector.update((_drowsy_pose(),))

    detector.update((_alert_pose(),))
    detector.update((_alert_pose(),))
    detector.update((_alert_pose(),))
    detector.update((_alert_pose(),))
    snapshot = detector.update((_alert_pose(),))

    assert snapshot.active is False
    assert snapshot.drowsy_count == 0


def test_detector_no_drowsiness_when_alert() -> None:
    detector = _detector(confirm_frames=1, release_frames=1)

    snapshot = detector.update((_alert_pose(),))

    assert snapshot.active is False
    assert snapshot.drowsy_count == 0


def test_detector_tracks_drowsy_people() -> None:
    detector = _detector(confirm_frames=1, release_frames=1)

    # One alert, one drowsy - should detect only one as drowsy.
    detector.update((_alert_pose(), _drowsy_pose()))
    snapshot = detector.update((_alert_pose(), _drowsy_pose()))

    assert snapshot.drowsy_count == 1
    assert snapshot.people == 2


def test_detector_empty_frame() -> None:
    detector = _detector(confirm_frames=1, release_frames=1)
    detector.update((_drowsy_pose(),))

    snapshot = detector.update(())

    assert snapshot.active is False


def test_detector_reset_clears_state() -> None:
    detector = _detector(confirm_frames=1)
    detector.update((_drowsy_pose(),))
    detector.reset()

    snapshot = detector.update((_alert_pose(),))

    assert snapshot.active is False


def test_detector_rejects_invalid_confirm_frames() -> None:
    with pytest.raises(ConfigError, match="confirm_frames"):
        _detector(confirm_frames=0)


def test_detector_rejects_invalid_release_frames() -> None:
    with pytest.raises(ConfigError, match="release_frames"):
        _detector(release_frames=0)


def test_detector_rejects_invalid_nodding_window() -> None:
    with pytest.raises(ConfigError, match="nodding_window"):
        _detector(nodding_window=0)


def test_detector_rejects_invalid_eye_close_frames() -> None:
    with pytest.raises(ConfigError, match="eye_close_frames"):
        _detector(eye_close_frames=0)


def test_detector_rejects_invalid_yawn_frames() -> None:
    with pytest.raises(ConfigError, match="yawn_frames"):
        _detector(yawn_frames=0)


def test_detector_confirms_with_low_ear() -> None:
    detector = _detector(confirm_frames=1, release_frames=1, ear_threshold=0.18, eye_close_frames=2)
    face = _make_face_mesh_result(ear=0.1)

    detector.update((_alert_pose(),), faces=(face,))
    detector.update((_alert_pose(),), faces=(face,))
    snapshot = detector.update((_alert_pose(),), faces=(face,))

    assert snapshot.active is True
    assert snapshot.ear_avg == 0.1


def test_detector_confirms_with_high_mar() -> None:
    detector = _detector(confirm_frames=1, release_frames=1, mar_threshold=0.5, yawn_frames=2)
    face = _make_face_mesh_result(mar=0.7)

    detector.update((_alert_pose(),), faces=(face,))
    detector.update((_alert_pose(),), faces=(face,))
    snapshot = detector.update((_alert_pose(),), faces=(face,))

    assert snapshot.active is True
    assert snapshot.mar == 0.7


def test_detector_releases_when_ear_recovers() -> None:
    detector = _detector(confirm_frames=1, release_frames=2, ear_threshold=0.18, eye_close_frames=2)
    face_closed = _make_face_mesh_result(ear=0.1)
    face_open = _make_face_mesh_result(ear=0.3)

    detector.update((_alert_pose(),), faces=(face_closed,))
    detector.update((_alert_pose(),), faces=(face_closed,))
    assert detector._active is True

    detector.update((_alert_pose(),), faces=(face_open,))
    detector.update((_alert_pose(),), faces=(face_open,))
    snapshot = detector.update((_alert_pose(),), faces=(face_open,))

    assert snapshot.active is False


def test_detector_confirms_face_only_low_ear() -> None:
    detector = _detector(confirm_frames=1, release_frames=1, ear_threshold=0.18, eye_close_frames=2)
    face = _make_face_mesh_result(ear=0.1)

    detector.update((), faces=(face,))
    detector.update((), faces=(face,))
    snapshot = detector.update((), faces=(face,))

    assert snapshot.active is True
    assert snapshot.drowsy_count == 1
    assert snapshot.people == 1
    assert snapshot.ear_avg == 0.1


def test_detector_confirms_face_only_high_mar() -> None:
    detector = _detector(confirm_frames=1, release_frames=1, mar_threshold=0.5, yawn_frames=2)
    face = _make_face_mesh_result(mar=0.7)

    detector.update((), faces=(face,))
    detector.update((), faces=(face,))
    snapshot = detector.update((), faces=(face,))

    assert snapshot.active is True
    assert snapshot.drowsy_count == 1
    assert snapshot.people == 1
    assert snapshot.mar == 0.7


def test_detector_face_only_no_drowsiness_when_alert() -> None:
    detector = _detector(confirm_frames=1, release_frames=1, ear_threshold=0.18, mar_threshold=0.5)
    face = _make_face_mesh_result(ear=0.3, mar=0.02)

    snapshot = detector.update((), faces=(face,))

    assert snapshot.active is False
    assert snapshot.drowsy_count == 0


# --- Configuracion ---


def test_drowsiness_config_defaults() -> None:
    config = DrowsinessConfig()

    assert config.model_path == DEFAULT_DROWSINESS_MODEL_PATH
    assert config.min_confidence == DEFAULT_DROWSINESS_MIN_CONFIDENCE
    assert config.min_keypoint_confidence == DEFAULT_DROWSINESS_KEYPOINT_CONFIDENCE
    assert config.head_droop_threshold == DEFAULT_DROWSINESS_HEAD_DROOP_THRESHOLD
    assert config.nod_amplitude_threshold == DEFAULT_DROWSINESS_NOD_AMPLITUDE_THRESHOLD
    assert config.nodding_window == DEFAULT_DROWSINESS_NODDING_WINDOW
    assert config.ear_threshold == DEFAULT_DROWSINESS_EAR_THRESHOLD
    assert config.eye_close_frames == DEFAULT_DROWSINESS_EYE_CLOSE_FRAMES
    assert config.mar_threshold == DEFAULT_DROWSINESS_MAR_THRESHOLD
    assert config.yawn_frames == DEFAULT_DROWSINESS_YAWN_FRAMES
    assert config.confirm_frames == DEFAULT_DROWSINESS_CONFIRM_FRAMES
    assert config.release_frames == DEFAULT_DROWSINESS_RELEASE_FRAMES
    assert config.alert == DrowsinessAlertConfig()


def test_drowsiness_config_rejects_invalid_values() -> None:
    with pytest.raises(ValidationError):
        DrowsinessConfig(confirm_frames=0)
    with pytest.raises(ValidationError):
        DrowsinessConfig(release_frames=0)
    with pytest.raises(ValidationError):
        DrowsinessConfig(head_droop_threshold=-0.1)
    with pytest.raises(ValidationError):
        DrowsinessAlertConfig(repeat_seconds=-0.1)


def test_app_config_includes_drowsiness() -> None:
    config = AppConfig()

    assert config.drowsiness == DrowsinessConfig()
    parsed = AppConfig.model_validate({"drowsiness": {"head_droop_threshold": 0.15}})
    assert parsed.drowsiness.head_droop_threshold == 0.15


def test_drowsiness_config_loads_from_yaml(tmp_path: Path) -> None:
    from recognizer.settings import load_config

    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "drowsiness:\n"
        "  head_droop_threshold: 0.15\n"
        "  ear_threshold: 0.2\n"
        "  mar_threshold: 0.4\n"
        "  alert:\n"
        "    repeat_seconds: 0\n",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.drowsiness.head_droop_threshold == 0.15
    assert config.drowsiness.ear_threshold == 0.2
    assert config.drowsiness.mar_threshold == 0.4
    assert config.drowsiness.alert.repeat_seconds == 0


# --- Menu y catalogo ---


def test_resolve_drowsiness_runner_is_lazy() -> None:
    before = set(sys.modules)

    assert resolve_runner(AppId.DROWSINESS) is run_drowsiness

    added = set(sys.modules) - before
    assert "ultralytics" not in added
    assert "torch" not in added


def test_drowsiness_catalog_entry_is_available() -> None:
    catalog = AppCatalog()

    info = catalog.require(AppId.DROWSINESS)
    assert info.implemented is True
    assert catalog.availability(AppId.DROWSINESS, enabled={}) is AppAvailability.AVAILABLE
    assert (
        catalog.availability(AppId.DROWSINESS, enabled={AppId.DROWSINESS: False})
        is AppAvailability.DISABLED
    )


def test_menu_renders_drowsiness_as_available() -> None:
    from recognizer.core.config import AppsConfig

    text = menu.render_catalog(AppCatalog(), AppsConfig())

    assert "Somnolencia" in text
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


class _FakePoseEstimatorCM:
    def __init__(self, config: DrowsinessConfig, script: list[tuple[Pose, ...]]) -> None:
        self.config = config
        self._script = script
        self.estimate_calls = 0

    def __enter__(self) -> "_FakePoseEstimatorCM":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def estimate(self, frame: Frame) -> tuple[Pose, ...]:
        _ = frame
        self.estimate_calls += 1
        if self._script:
            return self._script.pop(0)
        return ()


class _FakeFaceMeshCM:
    def __init__(self, script: list[tuple[FaceMeshResult, ...]]) -> None:
        self._script = script
        self.detect_calls = 0

    def __enter__(self) -> "_FakeFaceMeshCM":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def detect(self, frame: Frame) -> tuple[FaceMeshResult, ...]:
        _ = frame
        self.detect_calls += 1
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


_WORKERS: list["_FakeWorker"] = []


class _FakeSourceContext:
    """Context manager que devuelve la fuente sin arrancar el hilo de drenado."""

    def __init__(self, source: object) -> None:
        self._source = source

    def __enter__(self) -> object:
        return self._source

    def __exit__(self, *_exc_info: object) -> None:
        return None


class _FakeWorker:
    """Doble del worker de inferencia: no arranca hilo; expone infer/on_result."""

    def __init__(self, *, infer: object, on_result: object, **_kwargs: object) -> None:
        self.infer = infer
        self.on_result = on_result
        _WORKERS.append(self)

    def __enter__(self) -> "_FakeWorker":
        return self

    def __exit__(self, *_exc_info: object) -> None:
        return None

    @property
    def error(self) -> None:
        return None


class _DrivenSource:
    """Fuente que corre la inferencia del worker de forma sincrona en read()."""

    def __init__(self, camera: _FakeCamera) -> None:
        self._camera = camera

    def read(self) -> Frame | None:
        frame = self._camera.read()
        if frame is not None and _WORKERS:
            worker = _WORKERS[-1]
            worker.on_result(worker.infer(frame))  # type: ignore[operator]
        return frame


def _patch_runner_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    frames: list[Frame],
    script: list[tuple[Pose, ...]],
    face_script: list[tuple[FaceMeshResult, ...]] | None = None,
    app_config: AppConfig | None = None,
) -> tuple[_FakePoseEstimatorCM, _FakeFaceMeshCM, _FakeAlert, _FakeAlert]:
    resolved = app_config if app_config is not None else AppConfig()
    estimator = _FakePoseEstimatorCM(resolved.drowsiness, script)
    face_mesh = _FakeFaceMeshCM(face_script or [() for _ in script])
    sound = _FakeAlert()
    silent = _FakeAlert()
    _WORKERS.clear()

    def camera_factory(config: CameraConfig) -> _DrivenSource:
        return _DrivenSource(_FakeCamera(config, frames))

    monkeypatch.setattr(drowsiness_module, "prepare_workspace", lambda path: path)
    monkeypatch.setattr(drowsiness_module, "load_config", lambda path: resolved)  # noqa: ARG005
    monkeypatch.setattr(
        drowsiness_module,
        "resolve_camera_config",
        lambda *, app_config, device_override: CameraConfig(),  # noqa: ARG005
    )
    monkeypatch.setattr(drowsiness_module, "OpenCVCamera", camera_factory)
    monkeypatch.setattr(drowsiness_module, "LatestFrameSource", _FakeSourceContext)
    monkeypatch.setattr(drowsiness_module, "LatestInferenceWorker", _FakeWorker)
    monkeypatch.setattr(
        drowsiness_module,
        "UltralyticsPoseEstimator",
        lambda config: estimator,  # noqa: ARG005
    )
    monkeypatch.setattr(
        drowsiness_module,
        "MediaPipeFaceMesh",
        lambda config: face_mesh,  # noqa: ARG005
    )
    monkeypatch.setattr(drowsiness_module, "SystemSoundAlert", lambda: sound)
    monkeypatch.setattr(drowsiness_module, "SilentAlert", lambda: silent)
    monkeypatch.setattr(cv2, "destroyAllWindows", lambda: None)
    return estimator, face_mesh, sound, silent


def _app_config(
    *,
    alert_enabled: bool = True,
    repeat_seconds: float = 0.0,
    confirm_frames: int = 1,
    release_frames: int = 1,
) -> AppConfig:
    return AppConfig(
        drowsiness=DrowsinessConfig(
            confirm_frames=confirm_frames,
            release_frames=release_frames,
            alert=DrowsinessAlertConfig(enabled=alert_enabled, repeat_seconds=repeat_seconds),
        )
    )


@dataclass(frozen=True)
class _OverlayCall:
    active: bool
    drowsy_count: int


def _record_overlay(monkeypatch: pytest.MonkeyPatch) -> list[_OverlayCall]:
    calls: list[_OverlayCall] = []

    def fake_draw(
        image: NDArray[np.uint8],
        *,
        poses: tuple[Pose, ...],
        active: bool,
        drowsy_count: int,
        min_keypoint_confidence: float,
        ear_avg: float | None = None,
        mar: float | None = None,
        head_droop: float | None = None,
        nod_amplitude: float | None = None,
    ) -> None:
        _ = (image, poses, min_keypoint_confidence, ear_avg, mar, head_droop, nod_amplitude)
        calls.append(_OverlayCall(active=active, drowsy_count=drowsy_count))

    monkeypatch.setattr(drowsiness_module, "draw_drowsiness_overlay", fake_draw)
    return calls


def test_runner_rejects_headless_without_frames() -> None:
    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=0)

    assert run_drowsiness(request) == 1


def test_runner_confirms_drowsy_and_notifies(monkeypatch: pytest.MonkeyPatch) -> None:
    estimator, _face_mesh, sound, _silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame(), _frame()],
        script=[(_drowsy_pose(),), (_drowsy_pose(),)],
        app_config=_app_config(),
    )
    calls = _record_overlay(monkeypatch)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=2)
    assert run_drowsiness(request) == 0

    assert estimator.estimate_calls == 2
    assert sound.notify_calls == 1
    assert calls[1] == _OverlayCall(active=True, drowsy_count=1)


def test_runner_alert_does_not_notify(monkeypatch: pytest.MonkeyPatch) -> None:
    estimator, _face_mesh, sound, _silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame()],
        script=[(_alert_pose(),)],
        app_config=_app_config(),
    )
    calls = _record_overlay(monkeypatch)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=1)
    assert run_drowsiness(request) == 0

    assert estimator.estimate_calls == 1
    assert sound.notify_calls == 0
    assert calls[0] == _OverlayCall(active=False, drowsy_count=0)


def test_runner_detects_drowsy_face_without_body(monkeypatch: pytest.MonkeyPatch) -> None:
    config = AppConfig(
        drowsiness=DrowsinessConfig(
            confirm_frames=1,
            release_frames=1,
            ear_threshold=0.18,
            eye_close_frames=2,
            alert=DrowsinessAlertConfig(enabled=True, repeat_seconds=0.0),
        )
    )
    _estimator, face_mesh, sound, _silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame(), _frame()],
        script=[(), ()],  # sin pose: la camara no ve el cuerpo/brazos
        face_script=[
            (_make_face_mesh_result(ear=0.1),),
            (_make_face_mesh_result(ear=0.1),),
        ],
        app_config=config,
    )
    calls = _record_overlay(monkeypatch)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=2)
    assert run_drowsiness(request) == 0

    assert face_mesh.detect_calls == 2
    assert sound.notify_calls == 1
    assert calls[1] == _OverlayCall(active=True, drowsy_count=1)


def test_runner_repeats_alert_while_active(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    _estimator, _face_mesh, sound, _silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame(), _frame(), _frame()],
        script=[(_drowsy_pose(),), (_drowsy_pose(),), (_drowsy_pose(),)],
        app_config=_app_config(repeat_seconds=2.0),
    )
    times = iter([100.0, 100.5, 103.0])
    monkeypatch.setattr(time, "monotonic", lambda: next(times))

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=3)
    assert run_drowsiness(request) == 0

    assert sound.notify_calls == 2


def test_runner_with_alert_disabled_uses_silent_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _estimator, _face_mesh, sound, silent = _patch_runner_env(
        monkeypatch,
        frames=[_frame()],
        script=[(_drowsy_pose(),)],
        app_config=_app_config(alert_enabled=False),
    )

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=1)
    assert run_drowsiness(request) == 0

    assert sound.notify_calls == 0
    assert silent.close_calls >= 1
