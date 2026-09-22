"""Tests del desenfoque de privacidad (etapa 19), sin hardware real.

Cubre configuracion, catalogo, import perezoso del menu, dominio de regiones,
adaptador de blur/overlay, detector InsightFace con fachadas fake y runner con
camara y detector fakes (bucle real).
"""

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray
from pydantic import ValidationError

from recognizer.adapters import insightface_detector as detector_module
from recognizer.adapters.overlay_privacy import blur_faces, draw_privacy_overlay
from recognizer.cli import menu
from recognizer.cli.apps import privacy_blur as pb_module
from recognizer.cli.apps.privacy_blur import run_privacy_blur
from recognizer.cli.menu import resolve_runner
from recognizer.core.config import AppConfig, AppsConfig, CameraConfig, PrivacyBlurConfig
from recognizer.core.constants import (
    DEFAULT_PRIVACY_BLUR_STRENGTH,
    DEFAULT_PRIVACY_CONFIDENCE,
    DEFAULT_PRIVACY_DET_SIZE,
    DEFAULT_PRIVACY_FACE_MARGIN,
    DEFAULT_PRIVACY_MODEL_PATH,
)
from recognizer.core.domain.app import AppAvailability, AppCatalog, AppId, AppRunRequest
from recognizer.core.domain.face import FaceBox
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.privacy import PixelRect, effective_blur_kernel, face_blur_regions
from recognizer.core.errors import ConfigError, FaceDetectorError

FRAME_SHAPE = (64, 64, 3)
REQUEST = AppRunRequest(config_path=Path("config.yaml"))


def _box(
    x_min: float = 0.3,
    y_min: float = 0.3,
    x_max: float = 0.6,
    y_max: float = 0.6,
    confidence: float = 0.9,
) -> FaceBox:
    return FaceBox(
        x_min=x_min,
        y_min=y_min,
        x_max=x_max,
        y_max=y_max,
        confidence=confidence,
    )


def _frame() -> Frame:
    data: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    return Frame(data=data, timestamp=1.0)


def _noisy_image(seed: int = 0, shape: tuple[int, int, int] = FRAME_SHAPE) -> NDArray[np.uint8]:
    rng = np.random.default_rng(seed)
    image: NDArray[np.uint8] = rng.integers(0, 256, size=shape, dtype=np.uint8)
    return image


# --- Configuracion ---


def test_privacy_config_defaults() -> None:
    config = PrivacyBlurConfig()

    assert config.model_path == DEFAULT_PRIVACY_MODEL_PATH
    assert config.min_confidence == DEFAULT_PRIVACY_CONFIDENCE
    assert config.det_size == DEFAULT_PRIVACY_DET_SIZE
    assert config.blur_strength == DEFAULT_PRIVACY_BLUR_STRENGTH
    assert config.margin_ratio == DEFAULT_PRIVACY_FACE_MARGIN


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_privacy_config_rejects_bad_confidence(confidence: float) -> None:
    with pytest.raises(ValidationError):
        PrivacyBlurConfig(min_confidence=confidence)


@pytest.mark.parametrize("strength", [50, 2, 100])
def test_privacy_config_rejects_bad_blur_strength(strength: int) -> None:
    with pytest.raises(ValidationError):
        PrivacyBlurConfig(blur_strength=strength)


@pytest.mark.parametrize("det_size", [64, 2000])
def test_privacy_config_rejects_bad_det_size(det_size: int) -> None:
    with pytest.raises(ValidationError):
        PrivacyBlurConfig(det_size=det_size)


@pytest.mark.parametrize("margin", [-0.1, 1.1])
def test_privacy_config_rejects_bad_margin(margin: float) -> None:
    with pytest.raises(ValidationError):
        PrivacyBlurConfig(margin_ratio=margin)


def test_privacy_config_rejects_empty_model_path() -> None:
    with pytest.raises(ValidationError):
        PrivacyBlurConfig(model_path="")


def test_app_config_includes_privacy_blur() -> None:
    config = AppConfig()

    assert config.privacy_blur == PrivacyBlurConfig()
    parsed = AppConfig.model_validate({"privacy_blur": {"blur_strength": 31, "margin_ratio": 0.2}})
    assert parsed.privacy_blur.blur_strength == 31
    assert parsed.privacy_blur.margin_ratio == 0.2


# --- Catalogo y menu ---


def test_privacy_catalog_entry_is_available() -> None:
    catalog = AppCatalog()

    info = catalog.require(AppId.PRIVACY_BLUR)
    assert info.implemented is True
    assert catalog.availability(AppId.PRIVACY_BLUR, enabled={}) is AppAvailability.AVAILABLE
    assert (
        catalog.availability(AppId.PRIVACY_BLUR, enabled={AppId.PRIVACY_BLUR: False})
        is AppAvailability.DISABLED
    )


def test_resolve_privacy_runner_is_lazy() -> None:
    before = set(sys.modules)

    assert resolve_runner(AppId.PRIVACY_BLUR) is run_privacy_blur

    added = set(sys.modules) - before
    assert "insightface" not in added
    assert "onnxruntime" not in added


def test_menu_renders_privacy_blur_as_available() -> None:
    text = menu.render_catalog(AppCatalog(), AppsConfig())

    assert "Desenfoque privacidad" in text
    assert menu.LABEL_AVAILABLE in text


# --- Dominio: regiones y kernel ---


def test_face_blur_regions_expands_by_margin() -> None:
    regions = face_blur_regions((_box(),), width=100, height=100, margin_ratio=0.1)

    assert regions == (PixelRect(x_min=27, y_min=27, x_max=63, y_max=63),)
    assert regions[0].width == 36
    assert regions[0].height == 36


def test_face_blur_regions_without_margin_matches_box() -> None:
    regions = face_blur_regions((_box(),), width=100, height=100, margin_ratio=0.0)

    assert regions == (PixelRect(x_min=30, y_min=30, x_max=60, y_max=60),)


def test_face_blur_regions_clamps_to_frame() -> None:
    regions = face_blur_regions(
        (_box(x_min=0.0, y_min=0.0, x_max=0.2, y_max=0.2),),
        width=100,
        height=100,
        margin_ratio=1.0,
    )

    assert regions == (PixelRect(x_min=0, y_min=0, x_max=40, y_max=40),)


def test_face_blur_regions_skips_degenerate_boxes() -> None:
    tiny = FaceBox(x_min=0.5, y_min=0.5, x_max=0.505, y_max=0.505, confidence=0.9)

    regions = face_blur_regions((tiny,), width=64, height=64, margin_ratio=0.0)

    assert regions == ()


@pytest.mark.parametrize(("width", "height"), [(0, 10), (10, 0)])
def test_face_blur_regions_rejects_empty_frame(width: int, height: int) -> None:
    with pytest.raises(ConfigError):
        face_blur_regions((), width=width, height=height)


def test_face_blur_regions_rejects_negative_margin() -> None:
    with pytest.raises(ConfigError):
        face_blur_regions((), width=10, height=10, margin_ratio=-0.1)


@pytest.mark.parametrize(
    ("x_min", "y_min", "x_max", "y_max"),
    [(5, 0, 5, 10), (0, 5, 10, 5)],
)
def test_pixel_rect_rejects_degenerate_rectangles(
    x_min: int, y_min: int, x_max: int, y_max: int
) -> None:
    with pytest.raises(ConfigError):
        PixelRect(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)


def test_effective_blur_kernel_clamps_to_short_side() -> None:
    rect = PixelRect(x_min=0, y_min=0, x_max=40, y_max=100)

    assert effective_blur_kernel(strength=51, rect=rect) == 39
    assert effective_blur_kernel(strength=31, rect=rect) == 31


def test_effective_blur_kernel_zero_for_tiny_rect() -> None:
    rect = PixelRect(x_min=0, y_min=0, x_max=2, y_max=2)

    assert effective_blur_kernel(strength=51, rect=rect) == 0


@pytest.mark.parametrize("strength", [2, 100])
def test_effective_blur_kernel_rejects_out_of_range(strength: int) -> None:
    rect = PixelRect(x_min=0, y_min=0, x_max=40, y_max=40)

    with pytest.raises(ConfigError):
        effective_blur_kernel(strength=strength, rect=rect)


# --- Adaptador: blur y overlay ---


def test_blur_faces_changes_region_and_keeps_the_rest() -> None:
    image = _noisy_image()
    original = image.copy()

    regions = blur_faces(image, boxes=(_box(),), blur_strength=51, margin_ratio=0.0)

    assert len(regions) == 1
    rect = regions[0]
    assert not np.array_equal(
        image[rect.y_min : rect.y_max, rect.x_min : rect.x_max],
        original[rect.y_min : rect.y_max, rect.x_min : rect.x_max],
    )
    mask = np.ones(FRAME_SHAPE[:2], dtype=bool)
    mask[rect.y_min : rect.y_max, rect.x_min : rect.x_max] = False
    assert np.array_equal(image[mask], original[mask])


def test_blur_faces_skips_tiny_faces() -> None:
    image = _noisy_image()
    original = image.copy()
    tiny = FaceBox(x_min=0.5, y_min=0.5, x_max=0.505, y_max=0.505, confidence=0.9)

    regions = blur_faces(image, boxes=(tiny,), blur_strength=51, margin_ratio=0.0)

    assert regions == ()
    assert np.array_equal(image, original)


def test_blur_faces_without_boxes_does_nothing() -> None:
    image = _noisy_image()
    original = image.copy()

    assert blur_faces(image, boxes=(), blur_strength=51) == ()
    assert np.array_equal(image, original)


def test_draw_privacy_overlay_draws_hud_and_frames() -> None:
    image: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    regions = (PixelRect(x_min=5, y_min=5, x_max=30, y_max=30),)

    draw_privacy_overlay(image, regions=regions, blurred=1)

    assert image.shape == FRAME_SHAPE
    assert image.any()


def test_draw_privacy_overlay_without_regions_still_draws_hud() -> None:
    image: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)

    draw_privacy_overlay(image, regions=(), blurred=0)

    assert image.any()


# --- Detector InsightFace con fachadas fake ---


class _FakeBox:
    def __init__(self, coords: tuple[float, float, float, float]) -> None:
        self._coords = coords

    def __len__(self) -> int:
        return len(self._coords)

    def __getitem__(self, index: int) -> float:
        return self._coords[index]


class _FakeFace:
    def __init__(self, bbox: tuple[float, float, float, float], det_score: float) -> None:
        self.bbox = _FakeBox(bbox)
        self.det_score = det_score


class _FakeAnalysis:
    def __init__(self, faces: list[_FakeFace]) -> None:
        self._faces = faces
        self.prepared: tuple[int, tuple[int, int]] | None = None

    def prepare(self, *, ctx_id: int, det_size: tuple[int, int]) -> None:
        self.prepared = (ctx_id, det_size)

    def get(self, image_rgb: NDArray[np.uint8]) -> list[_FakeFace]:
        _ = image_rgb
        return list(self._faces)


def _patch_analysis(monkeypatch: pytest.MonkeyPatch, analysis: _FakeAnalysis) -> None:
    def fake_create(*, model_path: str, modules: tuple[str, ...]) -> _FakeAnalysis:
        _ = (model_path, modules)
        return analysis

    monkeypatch.setattr(detector_module, "create_analysis", fake_create)


def test_detection_facade_maps_and_filters_faces(monkeypatch: pytest.MonkeyPatch) -> None:
    analysis = _FakeAnalysis(
        [
            _FakeFace((10.0, 20.0, 60.0, 70.0), 0.9),
            _FakeFace((0.0, 0.0, 5.0, 5.0), 0.2),
            _FakeFace((0.0, 0.0, 5.0, 5.0), float("nan")),
        ]
    )
    _patch_analysis(monkeypatch, analysis)
    config = PrivacyBlurConfig()
    facade = detector_module.InsightFaceDetectionFacade(config)
    facade.open()

    frame: NDArray[np.uint8] = np.zeros((100, 100, 3), dtype=np.uint8)
    boxes = facade.detect(frame_bgr=frame, min_confidence=0.5)

    assert analysis.prepared == (0, (config.det_size, config.det_size))
    assert len(boxes) == 1
    assert boxes[0].x_min == pytest.approx(0.1)
    assert boxes[0].y_min == pytest.approx(0.2)
    assert boxes[0].x_max == pytest.approx(0.6)
    assert boxes[0].y_max == pytest.approx(0.7)
    assert boxes[0].confidence == pytest.approx(0.9)


def test_detection_facade_requires_open(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_analysis(monkeypatch, _FakeAnalysis([]))
    facade = detector_module.InsightFaceDetectionFacade(PrivacyBlurConfig())

    with pytest.raises(FaceDetectorError):
        facade.detect(frame_bgr=np.zeros(FRAME_SHAPE, dtype=np.uint8), min_confidence=0.5)


def test_detection_facade_rejects_double_open(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_analysis(monkeypatch, _FakeAnalysis([]))
    facade = detector_module.InsightFaceDetectionFacade(PrivacyBlurConfig())
    facade.open()

    with pytest.raises(FaceDetectorError):
        facade.open()


def test_detection_facade_wraps_analysis_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FailingAnalysis(_FakeAnalysis):
        def get(self, image_rgb: NDArray[np.uint8]) -> list[_FakeFace]:
            _ = image_rgb
            msg = "boom"
            raise RuntimeError(msg)

    _patch_analysis(monkeypatch, _FailingAnalysis([]))
    facade = detector_module.InsightFaceDetectionFacade(PrivacyBlurConfig())
    facade.open()

    with pytest.raises(FaceDetectorError):
        facade.detect(frame_bgr=np.zeros(FRAME_SHAPE, dtype=np.uint8), min_confidence=0.5)


def test_detection_facade_open_wraps_model_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_create(*, model_path: str, modules: tuple[str, ...]) -> _FakeAnalysis:
        _ = (model_path, modules)
        msg = "sin modelo"
        raise ImportError(msg)

    monkeypatch.setattr(detector_module, "create_analysis", failing_create)
    facade = detector_module.InsightFaceDetectionFacade(PrivacyBlurConfig())

    with pytest.raises(FaceDetectorError):
        facade.open()


def test_detection_facade_skips_degenerate_boxes(monkeypatch: pytest.MonkeyPatch) -> None:
    analysis = _FakeAnalysis([_FakeFace((10.0, 10.0, 10.0, 10.0), 0.9)])
    _patch_analysis(monkeypatch, analysis)
    facade = detector_module.InsightFaceDetectionFacade(PrivacyBlurConfig())
    facade.open()

    boxes = facade.detect(frame_bgr=np.zeros((100, 100, 3), dtype=np.uint8), min_confidence=0.5)

    assert boxes == ()


class _FakeFacade:
    def __init__(self, boxes: tuple[FaceBox, ...]) -> None:
        self._boxes = boxes
        self.opened = 0
        self.closed = 0

    def open(self) -> None:
        self.opened += 1

    def detect(self, *, frame_bgr: NDArray[np.uint8], min_confidence: float) -> tuple[FaceBox, ...]:
        _ = (frame_bgr, min_confidence)
        return self._boxes

    def close(self) -> None:
        self.closed += 1


def test_detector_class_lifecycle_with_fake_facade() -> None:
    facade = _FakeFacade((_box(),))
    detector = detector_module.InsightFaceFaceDetector(
        PrivacyBlurConfig(), facade_factory=lambda _config: facade
    )

    with pytest.raises(FaceDetectorError):
        detector.detect(_frame())

    with detector as opened:
        boxes = opened.detect(_frame())

    assert boxes == (_box(),)
    assert facade.opened == 1
    assert facade.closed == 1


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
        config: PrivacyBlurConfig,
        script: list[tuple[FaceBox, ...]],
    ) -> None:
        self.config = config
        self._script = script
        self.detect_calls = 0

    def __enter__(self) -> "_FakeDetectorCM":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def detect(self, frame: Frame) -> tuple[FaceBox, ...]:
        _ = frame
        self.detect_calls += 1
        if self._script:
            return self._script.pop(0)
        return ()


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
    script: list[tuple[FaceBox, ...]],
    app_config: AppConfig | None = None,
) -> _FakeDetectorCM:
    resolved = app_config if app_config is not None else AppConfig()
    detector = _FakeDetectorCM(resolved.privacy_blur, script)
    _WORKERS.clear()

    monkeypatch.setattr(pb_module, "prepare_workspace", lambda path: path)
    monkeypatch.setattr(pb_module, "load_config", lambda path: resolved)  # noqa: ARG005
    monkeypatch.setattr(
        pb_module,
        "resolve_camera_config",
        lambda *, app_config, device_override: CameraConfig(),  # noqa: ARG005
    )
    monkeypatch.setattr(
        pb_module, "OpenCVCamera", lambda config: _DrivenSource(_FakeCamera(config, frames))
    )
    monkeypatch.setattr(pb_module, "LatestFrameSource", _FakeSourceContext)
    monkeypatch.setattr(pb_module, "LatestInferenceWorker", _FakeWorker)
    monkeypatch.setattr(pb_module, "InsightFaceFaceDetector", lambda config: detector)  # noqa: ARG005
    monkeypatch.setattr(cv2, "destroyAllWindows", lambda: None)
    return detector


def test_runner_detects_and_blurs_headless(monkeypatch: pytest.MonkeyPatch) -> None:
    frames = [_frame(), _frame()]
    script: list[tuple[FaceBox, ...]] = [(_box(),), ()]
    detector = _patch_runner_env(monkeypatch, frames=frames, script=script)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=2)
    assert run_privacy_blur(request) == 0

    assert detector.detect_calls == 2


def test_runner_blurs_the_frame_in_place(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = Frame(data=_noisy_image(), timestamp=1.0)
    original = frame.data.copy()
    _patch_runner_env(monkeypatch, frames=[frame], script=[(_box(),)])

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=1)
    assert run_privacy_blur(request) == 0

    assert not np.array_equal(frame.data, original)


def test_runner_stops_on_quit_key_and_returns_to_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frames = [_frame(), _frame(), _frame()]
    script: list[tuple[FaceBox, ...]] = [(_box(),), (_box(),), (_box(),)]
    detector = _patch_runner_env(monkeypatch, frames=frames, script=script)
    keys = iter([0, ord("q")])
    shown: list[str] = []
    monkeypatch.setattr(cv2, "imshow", lambda name, _data: shown.append(name))
    monkeypatch.setattr(cv2, "waitKey", lambda _delay: next(keys))

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=True, max_frames=0)
    assert run_privacy_blur(request) == 0

    assert detector.detect_calls == 2
    assert shown == [pb_module.WINDOW_NAME, pb_module.WINDOW_NAME]


def test_runner_rejects_headless_without_frames() -> None:
    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=0)

    assert run_privacy_blur(request) == 1


def test_runner_returns_error_when_detector_fails_to_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_runner_env(monkeypatch, frames=[_frame()], script=[])

    class _FailingDetector:
        def __init__(self, config: PrivacyBlurConfig) -> None:
            self.config = config

        def __enter__(self) -> "_FailingDetector":
            msg = "sin modelo"
            raise FaceDetectorError(msg)

        def __exit__(self, *exc_info: object) -> None:
            return None

    monkeypatch.setattr(pb_module, "InsightFaceFaceDetector", _FailingDetector)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=1)
    assert run_privacy_blur(request) == 1
