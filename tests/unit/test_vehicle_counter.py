"""Tests del contador de vehiculos (etapa 18), sin hardware real.

Cubre configuracion, catalogo, import perezoso del menu, overlay y runner
con camara y detector fakes (bucle real).
"""

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray
from pydantic import ValidationError

from recognizer.cli import menu
from recognizer.cli.apps import vehicle_counter as vc_module
from recognizer.cli.apps.vehicle_counter import run_vehicle_counter
from recognizer.cli.menu import resolve_runner
from recognizer.core.config import (
    AppConfig,
    CameraConfig,
    CountingLineConfig,
    VehicleCounterConfig,
)
from recognizer.core.constants import (
    DEFAULT_VEHICLE_CONFIDENCE,
    DEFAULT_VEHICLE_MODEL_PATH,
    VEHICLE_LABEL,
)
from recognizer.core.domain.app import AppAvailability, AppCatalog, AppId, AppRunRequest
from recognizer.core.domain.detection import BoundingBox, Detection
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.tracking import CountingLine, LineAxis, TrackedDetection

FRAME_SHAPE = (48, 64, 3)
REQUEST = AppRunRequest(config_path=Path("config.yaml"))


def _bbox(
    x_min: float = 0.1,
    y_min: float = 0.2,
    x_max: float = 0.4,
    y_max: float = 0.8,
) -> BoundingBox:
    return BoundingBox(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)


def _bbox_at(*, x_min: float, x_max: float) -> BoundingBox:
    return BoundingBox(x_min=x_min, y_min=0.2, x_max=x_max, y_max=0.8)


def _tracked(
    track_id: int = 1,
    *,
    bbox: BoundingBox | None = None,
    label: str = VEHICLE_LABEL,
    confidence: float = 0.9,
) -> TrackedDetection:
    return TrackedDetection(
        track_id=track_id,
        detection=Detection(label=label, confidence=confidence, bbox=bbox or _bbox()),
    )


def _frame() -> Frame:
    data: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    return Frame(data=data, timestamp=1.0)


# --- Configuracion ---


def test_vehicle_counter_config_defaults() -> None:
    config = VehicleCounterConfig()

    assert config.model_path == DEFAULT_VEHICLE_MODEL_PATH
    assert config.min_confidence == DEFAULT_VEHICLE_CONFIDENCE
    assert config.target_label == VEHICLE_LABEL


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_vehicle_counter_config_rejects_bad_confidence(confidence: float) -> None:
    with pytest.raises(ValidationError):
        VehicleCounterConfig(min_confidence=confidence)


def test_vehicle_counter_config_rejects_empty_strings() -> None:
    with pytest.raises(ValidationError):
        VehicleCounterConfig(model_path="")
    with pytest.raises(ValidationError):
        VehicleCounterConfig(target_label="")


def test_app_config_includes_vehicle_counter() -> None:
    config = AppConfig()

    assert config.vehicle_counter == VehicleCounterConfig()
    parsed = AppConfig.model_validate(
        {"vehicle_counter": {"model_path": "models/x.pt", "min_confidence": 0.7}}
    )
    assert parsed.vehicle_counter.model_path == "models/x.pt"
    assert parsed.vehicle_counter.min_confidence == 0.7


# --- Catalogo y menu ---


def test_vehicle_counter_catalog_entry_is_available() -> None:
    catalog = AppCatalog()

    info = catalog.require(AppId.VEHICLE_COUNTER)
    assert info.implemented is True
    assert catalog.availability(AppId.VEHICLE_COUNTER, enabled={}) is AppAvailability.AVAILABLE
    assert (
        catalog.availability(AppId.VEHICLE_COUNTER, enabled={AppId.VEHICLE_COUNTER: False})
        is AppAvailability.DISABLED
    )


def test_resolve_vehicle_counter_runner_is_lazy() -> None:
    before = set(sys.modules)

    assert resolve_runner(AppId.VEHICLE_COUNTER) is run_vehicle_counter

    added = set(sys.modules) - before
    assert "ultralytics" not in added
    assert "torch" not in added


def test_menu_renders_vehicle_counter_as_available() -> None:
    from recognizer.core.config import AppsConfig

    text = menu.render_catalog(AppCatalog(), AppsConfig())

    assert "Conteo de autos" in text
    assert menu.LABEL_AVAILABLE in text


# --- Overlay ---


def test_draw_vehicle_overlay_runs_without_error() -> None:
    from recognizer.adapters.overlay_vehicle import draw_vehicle_overlay

    image: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    line = CountingLine(axis=LineAxis.VERTICAL, position=0.5, margin=0.05)

    draw_vehicle_overlay(
        image,
        tracked=(_tracked(1), _tracked(2)),
        current=2,
        entries=1,
        exits=0,
        line=line,
    )

    assert image.shape == FRAME_SHAPE


def test_draw_vehicle_overlay_without_line_runs() -> None:
    from recognizer.adapters.overlay_vehicle import draw_vehicle_overlay

    image: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)

    draw_vehicle_overlay(
        image,
        tracked=(),
        current=0,
        entries=0,
        exits=0,
        line=None,
    )

    assert image.shape == FRAME_SHAPE


def test_draw_vehicle_overlay_horizontal_line() -> None:
    from recognizer.adapters.overlay_vehicle import draw_vehicle_overlay

    image: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    line = CountingLine(axis=LineAxis.HORIZONTAL, position=0.5, margin=0.05)

    draw_vehicle_overlay(
        image,
        tracked=(),
        current=0,
        entries=0,
        exits=0,
        line=line,
    )

    assert image.shape == FRAME_SHAPE


# --- Runner con dobles (bucle de camara real) ---


class _FakeCamera:
    """Camara fake con guion de fotogramas y protocolo de contexto."""

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
    """Detector fake con guion por fotograma y protocolo de contexto."""

    def __init__(
        self,
        config: VehicleCounterConfig,
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


def _patch_runner_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    frames: list[Frame],
    script: list[tuple[TrackedDetection, ...]],
    app_config: AppConfig | None = None,
) -> _FakeDetectorCM:
    resolved = app_config if app_config is not None else AppConfig()
    detector = _FakeDetectorCM(resolved.vehicle_counter, script)

    monkeypatch.setattr(vc_module, "prepare_workspace", lambda path: path)
    monkeypatch.setattr(vc_module, "load_config", lambda path: resolved)  # noqa: ARG005
    monkeypatch.setattr(
        vc_module,
        "resolve_camera_config",
        lambda *, app_config, device_override: CameraConfig(),  # noqa: ARG005
    )
    monkeypatch.setattr(vc_module, "OpenCVCamera", lambda config: _FakeCamera(config, frames))
    monkeypatch.setattr(vc_module, "UltralyticsDetector", lambda config: detector)  # noqa: ARG005
    monkeypatch.setattr(cv2, "destroyAllWindows", lambda: None)
    return detector


def _app_config_with_line(
    *, enabled: bool, confirm_frames: int = 1, axis: LineAxis = LineAxis.VERTICAL
) -> AppConfig:
    return AppConfig(
        vehicle_counter=VehicleCounterConfig(
            line=CountingLineConfig(enabled=enabled, axis=axis, confirm_frames=confirm_frames)
        )
    )


def _record_overlay(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[int, int, int]]:
    calls: list[tuple[int, int, int]] = []

    def fake_draw(
        image: NDArray[np.uint8],
        *,
        tracked: tuple[TrackedDetection, ...],
        current: int,
        entries: int,
        exits: int,
        line: CountingLine | None,
    ) -> None:
        _ = (image, tracked, line)
        calls.append((current, entries, exits))

    monkeypatch.setattr(vc_module, "draw_vehicle_overlay", fake_draw)
    return calls


def test_runner_counts_and_draws_hud_headless(monkeypatch: pytest.MonkeyPatch) -> None:
    frames = [_frame(), _frame()]
    script: list[tuple[TrackedDetection, ...]] = [
        (_tracked(1), _tracked(2, confidence=0.8)),
        (_tracked(3, label="truck"),),
    ]
    detector = _patch_runner_env(monkeypatch, frames=frames, script=script)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=2)
    assert run_vehicle_counter(request) == 0

    assert detector.track_calls == 2


def test_runner_stops_on_quit_key_and_returns_to_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frames = [_frame(), _frame(), _frame()]
    script: list[tuple[TrackedDetection, ...]] = [
        (_tracked(1),),
        (_tracked(1),),
        (_tracked(1),),
    ]
    detector = _patch_runner_env(monkeypatch, frames=frames, script=script)
    keys = iter([0, ord("q")])
    shown: list[str] = []
    monkeypatch.setattr(cv2, "imshow", lambda name, _data: shown.append(name))
    monkeypatch.setattr(cv2, "waitKey", lambda _delay: next(keys))

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=True, max_frames=0)
    assert run_vehicle_counter(request) == 0

    assert detector.track_calls == 2
    assert shown == [vc_module.WINDOW_NAME, vc_module.WINDOW_NAME]


def test_runner_with_line_disabled_keeps_counts_at_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    script: list[tuple[TrackedDetection, ...]] = [
        (_tracked(1, bbox=_bbox_at(x_min=0.1, x_max=0.3)),),
        (_tracked(1, bbox=_bbox_at(x_min=0.7, x_max=0.9)),),
    ]
    _patch_runner_env(
        monkeypatch,
        frames=[_frame(), _frame()],
        script=script,
        app_config=_app_config_with_line(enabled=False),
    )
    calls = _record_overlay(monkeypatch)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=2)
    assert run_vehicle_counter(request) == 0

    assert calls == [(1, 0, 0), (1, 0, 0)]


def test_runner_with_line_enabled_accumulates_crossing_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script: list[tuple[TrackedDetection, ...]] = [
        (_tracked(1, bbox=_bbox_at(x_min=0.1, x_max=0.3)),),
        (_tracked(1, bbox=_bbox_at(x_min=0.7, x_max=0.9)),),
    ]
    _patch_runner_env(
        monkeypatch,
        frames=[_frame(), _frame()],
        script=script,
        app_config=_app_config_with_line(enabled=True, confirm_frames=1),
    )
    calls = _record_overlay(monkeypatch)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=2)
    assert run_vehicle_counter(request) == 0

    assert calls == [(1, 0, 0), (1, 1, 0)]


def test_runner_filters_non_target_label(monkeypatch: pytest.MonkeyPatch) -> None:
    """Solo cuenta vehiculos con el label configurado; ignora otros."""
    script: list[tuple[TrackedDetection, ...]] = [
        (_tracked(1, label=VEHICLE_LABEL), _tracked(2, label="person")),
    ]
    _patch_runner_env(
        monkeypatch,
        frames=[_frame()],
        script=script,
    )
    calls = _record_overlay(monkeypatch)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=1)
    assert run_vehicle_counter(request) == 0

    assert calls == [(1, 0, 0)]


def test_runner_rejects_headless_without_frames() -> None:
    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=0)

    assert run_vehicle_counter(request) == 1
