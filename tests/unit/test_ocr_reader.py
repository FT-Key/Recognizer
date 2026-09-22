"""Tests de OCR en vivo (etapa 23), sin hardware real.

Cubre dominio (ROI, OCRBox, OCRSnapshot), configuracion, adaptador EasyOCR
con fachadas fake, overlay, import perezoso del menu, catalogo, runner con
camara y motor fakes (bucle real) y worker asincrono de inferencia.
"""

import logging
import time
from collections import deque
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray
from pydantic import ValidationError

from recognizer.adapters.easyocr_engine import EasyOCREngine
from recognizer.adapters.latest_frame_source import LatestFrameSource
from recognizer.adapters.overlay_ocr import draw_ocr_overlay
from recognizer.cli.apps import ocr_reader as ocr_module
from recognizer.cli.apps.ocr_reader import _OCRWorker, run_ocr_reader
from recognizer.cli.menu import resolve_runner
from recognizer.core.config import AppConfig, CameraConfig, OCRReaderConfig
from recognizer.core.constants import (
    DEFAULT_OCR_CANVAS_SIZE,
    DEFAULT_OCR_CHANGE_THRESHOLD,
    DEFAULT_OCR_LANGUAGES,
    DEFAULT_OCR_MAG_RATIO,
    DEFAULT_OCR_MAX_FRAME_WIDTH,
    DEFAULT_OCR_MAX_INFERENCE_FPS,
    DEFAULT_OCR_MAX_RESULTS,
    DEFAULT_OCR_MAX_WIDTH,
    DEFAULT_OCR_MIN_CONFIDENCE,
    DEFAULT_OCR_PROCESS_EVERY_N_FRAMES,
    DEFAULT_OCR_ROI_X_MAX,
    DEFAULT_OCR_ROI_X_MIN,
    DEFAULT_OCR_ROI_Y_MAX,
    DEFAULT_OCR_ROI_Y_MIN,
)
from recognizer.core.domain.app import AppCatalog, AppId, AppRunRequest
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.ocr import ROI, OCRBox, OCRSnapshot

FRAME_SHAPE = (64, 64, 3)
REQUEST = AppRunRequest(config_path=Path("config.yaml"))


def _frame() -> Frame:
    data: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    return Frame(data=data, timestamp=1.0)


# ---------------------------------------------------------------------------
# Domain
# ---------------------------------------------------------------------------


class TestOCRBox:
    def test_frozen(self) -> None:
        box = OCRBox(x_min=0, y_min=0, x_max=10, y_max=10, text="hi", confidence=0.9)
        with pytest.raises(AttributeError):
            box.text = "no"  # type: ignore[misc]


class TestROI:
    def test_pixel_rect_full_frame(self) -> None:
        roi = ROI(x_min=0.0, y_min=0.0, x_max=1.0, y_max=1.0)
        assert roi.pixel_rect(640, 480) == (0, 0, 640, 480)

    def test_pixel_rect_center_crop(self) -> None:
        roi = ROI(x_min=0.25, y_min=0.25, x_max=0.75, y_max=0.75)
        assert roi.pixel_rect(100, 100) == (25, 25, 75, 75)

    def test_pixel_rect_non_square(self) -> None:
        roi = ROI(x_min=0.1, y_min=0.2, x_max=0.9, y_max=0.8)
        assert roi.pixel_rect(200, 100) == (20, 20, 180, 80)


class TestOCRSnapshot:
    def test_defaults(self) -> None:
        snap = OCRSnapshot(boxes=(), texts=(), roi=ROI(0, 0, 1, 1))
        assert snap.processed is True
        assert snap.boxes == ()
        assert snap.texts == ()


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestOCRReaderConfig:
    def test_defaults(self) -> None:
        cfg = OCRReaderConfig()
        assert cfg.languages == DEFAULT_OCR_LANGUAGES
        assert cfg.min_confidence == DEFAULT_OCR_MIN_CONFIDENCE
        assert cfg.process_every_n_frames == DEFAULT_OCR_PROCESS_EVERY_N_FRAMES
        assert cfg.max_results == DEFAULT_OCR_MAX_RESULTS
        assert cfg.max_inference_fps == DEFAULT_OCR_MAX_INFERENCE_FPS
        assert cfg.max_width == DEFAULT_OCR_MAX_WIDTH
        assert cfg.canvas_size == DEFAULT_OCR_CANVAS_SIZE
        assert cfg.mag_ratio == DEFAULT_OCR_MAG_RATIO
        assert cfg.max_frame_width == DEFAULT_OCR_MAX_FRAME_WIDTH
        assert cfg.change_threshold == DEFAULT_OCR_CHANGE_THRESHOLD
        assert cfg.roi_x_min == DEFAULT_OCR_ROI_X_MIN
        assert cfg.roi_y_min == DEFAULT_OCR_ROI_Y_MIN
        assert cfg.roi_x_max == DEFAULT_OCR_ROI_X_MAX
        assert cfg.roi_y_max == DEFAULT_OCR_ROI_Y_MAX

    def test_roi_x_min_ge_x_max_raises(self) -> None:
        with pytest.raises(ValidationError, match="roi_x_min < roi_x_max"):
            OCRReaderConfig(roi_x_min=0.8, roi_x_max=0.2)

    def test_roi_y_min_ge_y_max_raises(self) -> None:
        with pytest.raises(ValidationError, match="roi_y_min < roi_y_max"):
            OCRReaderConfig(roi_y_min=0.8, roi_y_max=0.2)

    def test_min_length_languages(self) -> None:
        with pytest.raises(ValidationError):
            OCRReaderConfig(languages=())

    def test_custom_values(self) -> None:
        cfg = OCRReaderConfig(
            languages=("en",),
            min_confidence=0.5,
            process_every_n_frames=5,
            max_results=10,
            max_inference_fps=1.5,
            roi_x_min=0.2,
            roi_y_min=0.2,
            roi_x_max=0.8,
            roi_y_max=0.8,
        )
        assert cfg.languages == ("en",)
        assert cfg.min_confidence == 0.5
        assert cfg.process_every_n_frames == 5
        assert cfg.max_results == 10
        assert cfg.max_inference_fps == 1.5

    def test_max_inference_fps_negative_raises(self) -> None:
        with pytest.raises(ValidationError):
            OCRReaderConfig(max_inference_fps=-1.0)


# ---------------------------------------------------------------------------
# EasyOCR adapter (faked)
# ---------------------------------------------------------------------------


class _FakeReader:
    """Fachada que simula easyocr.Reader.readtext()."""

    def __init__(self, results: list[Any]) -> None:
        self._results = results
        self.last_shape: tuple[int, ...] | None = None
        self.last_kwargs: dict[str, Any] = {}

    def readtext(self, crop: Any, **kwargs: Any) -> list[Any]:
        self.last_shape = getattr(crop, "shape", None)
        self.last_kwargs = kwargs
        return self._results


class TestEasyOCREngine:
    def test_read_before_open_returns_empty(self) -> None:
        engine = EasyOCREngine(languages=("en",), min_confidence=0.3, max_results=20)
        image = np.zeros(FRAME_SHAPE, dtype=np.uint8)
        roi = ROI(x_min=0.0, y_min=0.0, x_max=1.0, y_max=1.0)
        result = engine.read(image, roi, frame_width=64, frame_height=64)
        assert result == ()

    def test_read_filters_low_confidence(self) -> None:
        engine = EasyOCREngine(languages=("en",), min_confidence=0.5, max_results=20)
        engine._reader = _FakeReader(
            [
                [[(10, 10), (50, 10), (50, 30), (10, 30)], "hello", 0.9],
                [[(10, 40), (50, 40), (50, 60), (10, 60)], "weak", 0.2],
            ]
        )
        image = np.zeros(FRAME_SHAPE, dtype=np.uint8)
        roi = ROI(x_min=0.0, y_min=0.0, x_max=1.0, y_max=1.0)
        result = engine.read(image, roi, frame_width=64, frame_height=64)
        assert len(result) == 1
        assert result[0].text == "hello"
        assert result[0].confidence == pytest.approx(0.9)

    def test_read_respects_max_results(self) -> None:
        items = [[[(10, 10), (50, 10), (50, 30), (10, 30)], f"t{i}", 0.9] for i in range(10)]
        engine = EasyOCREngine(languages=("en",), min_confidence=0.1, max_results=3)
        engine._reader = _FakeReader(items)
        image = np.zeros(FRAME_SHAPE, dtype=np.uint8)
        roi = ROI(x_min=0.0, y_min=0.0, x_max=1.0, y_max=1.0)
        result = engine.read(image, roi, frame_width=64, frame_height=64)
        assert len(result) == 3

    def test_read_skips_malformed_items(self) -> None:
        engine = EasyOCREngine(languages=("en",), min_confidence=0.1, max_results=20)
        engine._reader = _FakeReader(
            [
                "not_a_list",
                [123],
                [[(10, 10), (50, 10), (50, 30), (10, 30)], "valid", 0.8],
            ]
        )
        image = np.zeros(FRAME_SHAPE, dtype=np.uint8)
        roi = ROI(x_min=0.0, y_min=0.0, x_max=1.0, y_max=1.0)
        result = engine.read(image, roi, frame_width=64, frame_height=64)
        assert len(result) == 1
        assert result[0].text == "valid"

    def test_read_with_roi_offset(self) -> None:
        engine = EasyOCREngine(languages=("en",), min_confidence=0.1, max_results=20)
        engine._reader = _FakeReader([[[(5, 5), (15, 5), (15, 15), (5, 15)], "offset", 0.95]])
        image = np.zeros((64, 64, 3), dtype=np.uint8)
        roi = ROI(x_min=0.25, y_min=0.25, x_max=0.75, y_max=0.75)
        result = engine.read(image, roi, frame_width=64, frame_height=64)
        assert len(result) == 1
        box = result[0]
        assert box.text == "offset"
        assert box.x_min == 21
        assert box.y_min == 21

    def test_read_empty_crop_returns_empty(self) -> None:
        engine = EasyOCREngine(languages=("en",), min_confidence=0.1, max_results=20)
        engine._reader = _FakeReader([])
        image = np.zeros((64, 64, 3), dtype=np.uint8)
        roi = ROI(x_min=0.5, y_min=0.5, x_max=0.5, y_max=0.5)
        result = engine.read(image, roi, frame_width=64, frame_height=64)
        assert result == ()

    def test_read_downscales_wide_crop(self) -> None:
        reader = _FakeReader([[[(10, 5), (30, 5), (30, 15), (10, 15)], "big", 0.9]])
        engine = EasyOCREngine(languages=("en",), min_confidence=0.1, max_results=20, max_width=100)
        engine._reader = reader
        image = np.zeros((100, 200, 3), dtype=np.uint8)
        roi = ROI(x_min=0.0, y_min=0.0, x_max=1.0, y_max=1.0)
        result = engine.read(image, roi, frame_width=200, frame_height=100)
        assert reader.last_shape is not None
        assert reader.last_shape[1] == 100
        assert reader.last_kwargs["paragraph"] is False
        assert reader.last_kwargs["batch_size"] == 1
        assert len(result) == 1
        box = result[0]
        # crop 200 px -> 100 px (escala 0.5): las cajas se duplican al mapear.
        assert box.x_min == 20
        assert box.y_min == 10
        assert box.x_max == 60
        assert box.y_max == 30

    def test_read_skips_downscale_when_max_width_zero(self) -> None:
        reader = _FakeReader([])
        engine = EasyOCREngine(languages=("en",), min_confidence=0.1, max_results=20, max_width=0)
        engine._reader = reader
        image = np.zeros((100, 200, 3), dtype=np.uint8)
        roi = ROI(x_min=0.0, y_min=0.0, x_max=1.0, y_max=1.0)
        engine.read(image, roi, frame_width=200, frame_height=100)
        assert reader.last_shape is not None
        assert reader.last_shape[1] == 200

    def test_close_resets_reader(self) -> None:
        engine = EasyOCREngine(languages=("en",), min_confidence=0.3, max_results=20)
        engine._reader = _FakeReader([])
        engine.close()
        assert engine._reader is None


# ---------------------------------------------------------------------------
# Overlay
# ---------------------------------------------------------------------------


class TestOCROverlay:
    def test_draw_ocr_overlay_runs_without_error(self) -> None:
        image = np.zeros(FRAME_SHAPE, dtype=np.uint8)
        boxes = (OCRBox(x_min=10, y_min=10, x_max=50, y_max=30, text="hello", confidence=0.9),)
        roi = ROI(x_min=0.1, y_min=0.1, x_max=0.9, y_max=0.9)
        draw_ocr_overlay(image, boxes=boxes, roi=roi, texts=("hello",))

    def test_draw_empty_overlay(self) -> None:
        image = np.zeros(FRAME_SHAPE, dtype=np.uint8)
        draw_ocr_overlay(image, boxes=(), roi=ROI(0, 0, 1, 1), texts=())

    def test_draw_many_texts_truncates_hud(self) -> None:
        image = np.zeros(FRAME_SHAPE, dtype=np.uint8)
        texts = tuple(f"text_{i}" for i in range(10))
        draw_ocr_overlay(image, boxes=(), roi=ROI(0, 0, 1, 1), texts=texts)


# ---------------------------------------------------------------------------
# Menu import + catalog
# ---------------------------------------------------------------------------


class TestMenuImport:
    def test_lazy_import(self) -> None:
        import sys

        sys.modules.pop("recognizer.cli.apps.ocr_reader", None)
        assert "recognizer.cli.apps.ocr_reader" not in sys.modules
        resolve_runner(AppId.OCR_READER)
        assert "recognizer.cli.apps.ocr_reader" in sys.modules

    def test_catalog_implemented(self) -> None:
        catalog = AppCatalog()
        info = catalog.by_id(AppId.OCR_READER)
        assert info is not None
        assert info.implemented is True


# ---------------------------------------------------------------------------
# Runner con dobles (bucle de camara real)
# ---------------------------------------------------------------------------


class _FakeCamera:
    """Camara fake que entrega N frames y luego cierra."""

    def __init__(self, config: CameraConfig, frames: list[Frame]) -> None:  # noqa: ARG002
        self._frames = list(frames)
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


class _FakeOCREngineCM:
    """Motor OCR fake con soporte de context manager para el runner."""

    def __init__(
        self,
        *,
        languages: tuple[str, ...] = ("en",),  # noqa: ARG002
        min_confidence: float = 0.3,  # noqa: ARG002
        max_results: int = 20,  # noqa: ARG002
        read_results: list[tuple[OCRBox, ...]] | None = None,
    ) -> None:
        self._read_results = read_results or [()]
        self._call_idx = 0
        self.opened = 0
        self.closed = 0

    def open(self) -> None:
        self.opened += 1

    def read(
        self,
        image_rgb: Any,  # noqa: ARG002
        roi: ROI,  # noqa: ARG002
        *,
        frame_width: int,  # noqa: ARG002
        frame_height: int,  # noqa: ARG002
    ) -> tuple[OCRBox, ...]:
        idx = self._call_idx
        self._call_idx += 1
        if idx < len(self._read_results):
            return self._read_results[idx]
        return ()

    def close(self) -> None:
        self.closed += 1


class _FakeSourceContext:
    """Context manager que devuelve la fuente sin arrancar el hilo de drenado."""

    def __init__(self, source: object) -> None:
        self._source = source

    def __enter__(self) -> object:
        return self._source

    def __exit__(self, *_exc_info: object) -> None:
        return None


class _FakeWorker:
    """Doble del worker de OCR: el runner no corre inferencia real."""

    def __init__(self, **_kwargs: object) -> None:
        pass

    def __enter__(self) -> "_FakeWorker":
        return self

    def __exit__(self, *_exc_info: object) -> None:
        return None

    @property
    def error(self) -> None:
        return None


def _patch_runner_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    frames: list[Frame],
    read_results: list[tuple[OCRBox, ...]] | None = None,
) -> _FakeOCREngineCM:
    """Parchea camera, engine, fuente y worker para el runner."""
    engine = _FakeOCREngineCM(read_results=read_results)

    monkeypatch.setattr(ocr_module, "prepare_workspace", lambda path: path)
    monkeypatch.setattr(ocr_module, "load_config", lambda _path: AppConfig())
    monkeypatch.setattr(
        ocr_module,
        "resolve_camera_config",
        lambda **_: CameraConfig(),
    )
    monkeypatch.setattr(ocr_module, "OpenCVCamera", lambda config: _FakeCamera(config, frames))
    monkeypatch.setattr(ocr_module, "EasyOCREngine", lambda **_kw: engine)
    monkeypatch.setattr(ocr_module, "LatestFrameSource", lambda camera: _FakeSourceContext(camera))
    monkeypatch.setattr(ocr_module, "_OCRWorker", _FakeWorker)
    monkeypatch.setattr(cv2, "destroyAllWindows", lambda: None)
    monkeypatch.setattr(ocr_module, "_opencv_gui_available", lambda: True)
    return engine


def test_runner_detects_text_headless(monkeypatch: pytest.MonkeyPatch) -> None:
    frames = [_frame(), _frame()]
    box = OCRBox(x_min=10, y_min=10, x_max=50, y_max=30, text="hola", confidence=0.9)
    engine = _patch_runner_env(monkeypatch, frames=frames, read_results=[(box,), ()])

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=2)
    assert run_ocr_reader(request) == 0
    assert engine.opened == 1
    assert engine.closed == 1


def test_runner_stops_on_quit_key(monkeypatch: pytest.MonkeyPatch) -> None:
    frames = [_frame(), _frame(), _frame()]
    _patch_runner_env(monkeypatch, frames=frames, read_results=[(), (), ()])
    keys = iter([0, ord("q")])
    shown: list[str] = []
    monkeypatch.setattr(cv2, "imshow", lambda name, _data: shown.append(name))
    monkeypatch.setattr(cv2, "waitKey", lambda _delay: next(keys))

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=True, max_frames=0)
    assert run_ocr_reader(request) == 0


def test_runner_stops_on_esc(monkeypatch: pytest.MonkeyPatch) -> None:
    frames = [_frame(), _frame()]
    _patch_runner_env(monkeypatch, frames=frames, read_results=[(), ()])
    keys = iter([0, 27])
    shown: list[str] = []
    monkeypatch.setattr(cv2, "imshow", lambda name, _data: shown.append(name))
    monkeypatch.setattr(cv2, "waitKey", lambda _delay: next(keys))

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=True, max_frames=0)
    assert run_ocr_reader(request) == 0


def test_runner_no_window_requires_frames() -> None:
    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=0)
    assert run_ocr_reader(request) == 1


def test_runner_headless_fallback_when_gui_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    frames = [_frame(), _frame()]
    engine = _patch_runner_env(monkeypatch, frames=frames, read_results=[(), ()])
    monkeypatch.setattr(ocr_module, "_opencv_gui_available", lambda: False)
    monkeypatch.setattr(cv2, "imshow", lambda _name, _data: None)
    monkeypatch.setattr(cv2, "waitKey", lambda _delay: 0)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=True, max_frames=2)
    assert run_ocr_reader(request) == 0
    assert engine.opened == 1
    assert engine.closed == 1


def test_runner_max_frames_exits_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    frames = [_frame(), _frame()]
    _patch_runner_env(monkeypatch, frames=frames, read_results=[(), ()])
    shown: list[str] = []
    monkeypatch.setattr(cv2, "imshow", lambda name, _data: shown.append(name))
    monkeypatch.setattr(cv2, "waitKey", lambda _delay: 0)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=True, max_frames=2)
    assert run_ocr_reader(request) == 0


# ---------------------------------------------------------------------------
# Worker de OCR (hilo real sobre LatestFrameSource fake)
# ---------------------------------------------------------------------------

TEST_LOGGER = logging.getLogger("test.ocr.worker")
WORKER_TIMEOUT = 2.0


class _PushSource:
    """Fuente falsa que entrega los fotogramas empujados por el test."""

    def __init__(self) -> None:
        self.frames: deque[Frame] = deque()

    def push(self, value: int) -> None:
        data: NDArray[np.uint8] = np.full(FRAME_SHAPE, value, dtype=np.uint8)
        self.frames.append(Frame(data=data, timestamp=float(value)))

    def open(self) -> None:
        pass

    def read(self) -> Frame | None:
        return self.frames.popleft() if self.frames else None

    def release(self) -> None:
        pass


class _CountingEngine:
    """Motor OCR fake que cuenta llamadas y devuelve cajas fijas."""

    def __init__(self, *, boxes: tuple[OCRBox, ...] = ()) -> None:
        self.calls = 0
        self.last_size: tuple[int, int] | None = None
        self._boxes = boxes

    def read(
        self,
        _image_rgb: Any,
        _roi: ROI,
        *,
        frame_width: int,
        frame_height: int,
    ) -> tuple[OCRBox, ...]:
        self.calls += 1
        self.last_size = (frame_width, frame_height)
        return self._boxes


class _FailingEngine:
    """Motor OCR fake que falla al leer."""

    def read(
        self,
        _image_rgb: Any,
        _roi: ROI,
        *,
        frame_width: int,  # noqa: ARG002
        frame_height: int,  # noqa: ARG002
    ) -> tuple[OCRBox, ...]:
        msg = "fallo simulado"
        raise RuntimeError(msg)


def _wait_until(predicate: Any, *, timeout: float = WORKER_TIMEOUT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_worker_publishes_boxes_and_stops() -> None:
    fake = _PushSource()
    source = LatestFrameSource(fake, read_timeout=0.5, join_timeout=1.0, failure_sleep=0.001)
    box = OCRBox(x_min=1, y_min=1, x_max=5, y_max=5, text="hola", confidence=0.9)
    engine = _CountingEngine(boxes=(box,))
    results: list[tuple[OCRBox, ...]] = []
    with source:
        worker = _OCRWorker(
            source=source,
            engine=engine,  # type: ignore[arg-type]
            roi=ROI(0, 0, 1, 1),
            process_every_n_frames=1,
            on_result=results.append,
            logger=TEST_LOGGER,
        )
        with worker:
            fake.push(1)
            assert _wait_until(lambda: bool(results))
        assert worker.error is None

    assert results[0] == (box,)
    assert engine.calls >= 1


def test_worker_throttles_inference_rate() -> None:
    fake = _PushSource()
    source = LatestFrameSource(fake, read_timeout=0.5, join_timeout=1.0, failure_sleep=0.001)
    engine = _CountingEngine()
    results: list[tuple[OCRBox, ...]] = []
    with source:
        worker = _OCRWorker(
            source=source,
            engine=engine,  # type: ignore[arg-type]
            roi=ROI(0, 0, 1, 1),
            process_every_n_frames=1,
            on_result=results.append,
            logger=TEST_LOGGER,
            max_inference_fps=1.0,
        )
        with worker:
            fake.push(1)
            assert _wait_until(lambda: bool(results))
            for value in range(2, 8):
                fake.push(value)
            time.sleep(0.15)
        assert worker.error is None

    assert len(results) == 1


def test_worker_captures_inference_error() -> None:
    fake = _PushSource()
    source = LatestFrameSource(fake, read_timeout=0.5, join_timeout=1.0, failure_sleep=0.001)
    with source:
        worker = _OCRWorker(
            source=source,
            engine=_FailingEngine(),  # type: ignore[arg-type]
            roi=ROI(0, 0, 1, 1),
            process_every_n_frames=1,
            on_result=lambda _boxes: None,
            logger=TEST_LOGGER,
        )
        with worker:
            fake.push(1)
            assert _wait_until(lambda: worker.error is not None)

    assert worker.error is not None


def test_worker_skips_unchanged_frames() -> None:
    fake = _PushSource()
    source = LatestFrameSource(fake, read_timeout=0.5, join_timeout=1.0, failure_sleep=0.001)
    engine = _CountingEngine()
    results: list[tuple[OCRBox, ...]] = []
    with source:
        worker = _OCRWorker(
            source=source,
            engine=engine,  # type: ignore[arg-type]
            roi=ROI(0, 0, 1, 1),
            process_every_n_frames=1,
            on_result=results.append,
            logger=TEST_LOGGER,
            change_threshold=5.0,
        )
        with worker:
            fake.push(1)
            assert _wait_until(lambda: bool(results))
            calls_after_first = engine.calls
            for _ in range(6):
                fake.push(1)
            time.sleep(0.2)
        assert worker.error is None

    assert engine.calls == calls_after_first


def test_worker_processes_changed_frames() -> None:
    fake = _PushSource()
    source = LatestFrameSource(fake, read_timeout=0.5, join_timeout=1.0, failure_sleep=0.001)
    engine = _CountingEngine()
    results: list[tuple[OCRBox, ...]] = []
    with source:
        worker = _OCRWorker(
            source=source,
            engine=engine,  # type: ignore[arg-type]
            roi=ROI(0, 0, 1, 1),
            process_every_n_frames=1,
            on_result=results.append,
            logger=TEST_LOGGER,
            change_threshold=5.0,
        )
        with worker:
            fake.push(1)
            assert _wait_until(lambda: bool(results))
            fake.push(200)
            assert _wait_until(lambda: engine.calls >= 2)
        assert worker.error is None

    assert engine.calls >= 2


def test_worker_downscales_frame_and_rescales_boxes() -> None:
    fake = _PushSource()
    source = LatestFrameSource(fake, read_timeout=0.5, join_timeout=1.0, failure_sleep=0.001)
    box = OCRBox(x_min=10, y_min=10, x_max=50, y_max=30, text="hi", confidence=0.9)
    engine = _CountingEngine(boxes=(box,))
    results: list[tuple[OCRBox, ...]] = []
    with source:
        worker = _OCRWorker(
            source=source,
            engine=engine,  # type: ignore[arg-type]
            roi=ROI(0, 0, 1, 1),
            process_every_n_frames=1,
            on_result=results.append,
            logger=TEST_LOGGER,
            max_frame_width=32,
        )
        with worker:
            fake.push(1)
            assert _wait_until(lambda: bool(results))
        assert worker.error is None

    # fotograma de 64 px -> 32 px (escala 0.5): la inferencia ve 32x32...
    assert engine.last_size == (32, 32)
    # ...y las cajas se duplican al volver al fotograma original.
    assert results[0][0].x_min == 20
    assert results[0][0].x_max == 100
    assert results[0][0].y_min == 20
    assert results[0][0].y_max == 60
