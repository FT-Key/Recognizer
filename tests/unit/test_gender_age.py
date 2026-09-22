"""Tests de edad y genero (etapa 21), sin hardware real.

Cubre configuracion, catalogo, import perezoso del menu, dominio de suavizado
(emparejado por IoU, mediana y voto de genero), adaptador InsightFace con
fachadas fake, overlay y runner con camara y estimador fakes (bucle real).
"""

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray
from pydantic import ValidationError

from recognizer.adapters import insightface_attributes as attrs_module
from recognizer.adapters.overlay_gender_age import draw_gender_age_overlay
from recognizer.cli import menu
from recognizer.cli.apps import gender_age as ga_module
from recognizer.cli.apps.gender_age import run_gender_age
from recognizer.cli.menu import resolve_runner
from recognizer.core.config import AppConfig, AppsConfig, CameraConfig, GenderAgeConfig
from recognizer.core.constants import (
    DEFAULT_GENDER_AGE_CONFIDENCE,
    DEFAULT_GENDER_AGE_DET_SIZE,
    DEFAULT_GENDER_AGE_MODEL_PATH,
    DEFAULT_GENDER_AGE_SMOOTHING_WINDOW,
    ESC_KEY,
    GENDER_AGE_IOU_THRESHOLD,
    GENDER_AGE_MAX_MISSES,
    MAX_ESTIMATED_AGE,
    MIN_ESTIMATED_AGE,
)
from recognizer.core.domain.app import AppAvailability, AppCatalog, AppId, AppRunRequest
from recognizer.core.domain.face import FaceBox
from recognizer.core.domain.face_attributes import (
    AgeGenderSmoother,
    FaceAttributes,
    FaceGender,
    intersection_over_union,
)
from recognizer.core.domain.frame import Frame
from recognizer.core.errors import ConfigError, FaceAttributeError
from recognizer.core.ports.face_attributes import FaceAttributeEstimatorConfig

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


def _face(
    box: FaceBox,
    *,
    age: int = 30,
    gender: FaceGender = FaceGender.MALE,
) -> FaceAttributes:
    return FaceAttributes(box=box, age=age, gender=gender)


def _frame() -> Frame:
    data: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    return Frame(data=data, timestamp=1.0)


def _noisy_image(seed: int = 0, shape: tuple[int, int, int] = FRAME_SHAPE) -> NDArray[np.uint8]:
    rng = np.random.default_rng(seed)
    image: NDArray[np.uint8] = rng.integers(0, 256, size=shape, dtype=np.uint8)
    return image


# --- Configuracion ---


def test_gender_age_config_defaults() -> None:
    config = GenderAgeConfig()

    assert config.model_path == DEFAULT_GENDER_AGE_MODEL_PATH
    assert config.min_confidence == DEFAULT_GENDER_AGE_CONFIDENCE
    assert config.det_size == DEFAULT_GENDER_AGE_DET_SIZE
    assert config.smoothing_window == DEFAULT_GENDER_AGE_SMOOTHING_WINDOW


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_gender_age_config_rejects_bad_confidence(confidence: float) -> None:
    with pytest.raises(ValidationError):
        GenderAgeConfig(min_confidence=confidence)


@pytest.mark.parametrize("det_size", [64, 2000])
def test_gender_age_config_rejects_bad_det_size(det_size: int) -> None:
    with pytest.raises(ValidationError):
        GenderAgeConfig(det_size=det_size)


@pytest.mark.parametrize("window", [0, 121])
def test_gender_age_config_rejects_bad_smoothing_window(window: int) -> None:
    with pytest.raises(ValidationError):
        GenderAgeConfig(smoothing_window=window)


def test_gender_age_config_rejects_empty_model_path() -> None:
    with pytest.raises(ValidationError):
        GenderAgeConfig(model_path="")


def test_app_config_includes_gender_age() -> None:
    config = AppConfig()

    assert config.gender_age == GenderAgeConfig()
    parsed = AppConfig.model_validate({"gender_age": {"det_size": 320, "smoothing_window": 3}})
    assert parsed.gender_age.det_size == 320
    assert parsed.gender_age.smoothing_window == 3


def _read_estimator_config(config: FaceAttributeEstimatorConfig) -> tuple[str, float, int]:
    return config.model_path, config.min_confidence, config.det_size


def test_gender_age_config_satisfies_estimator_port() -> None:
    assert _read_estimator_config(GenderAgeConfig()) == (
        DEFAULT_GENDER_AGE_MODEL_PATH,
        DEFAULT_GENDER_AGE_CONFIDENCE,
        DEFAULT_GENDER_AGE_DET_SIZE,
    )


# --- Catalogo y menu ---


def test_gender_age_catalog_entry_is_available() -> None:
    catalog = AppCatalog()

    info = catalog.require(AppId.GENDER_AGE)
    assert info.implemented is True
    assert catalog.availability(AppId.GENDER_AGE, enabled={}) is AppAvailability.AVAILABLE
    assert (
        catalog.availability(AppId.GENDER_AGE, enabled={AppId.GENDER_AGE: False})
        is AppAvailability.DISABLED
    )


def test_resolve_gender_age_runner_is_lazy() -> None:
    before = set(sys.modules)

    assert resolve_runner(AppId.GENDER_AGE) is run_gender_age

    added = set(sys.modules) - before
    assert "insightface" not in added
    assert "onnxruntime" not in added


def test_menu_renders_gender_age_as_available() -> None:
    text = menu.render_catalog(AppCatalog(), AppsConfig())

    assert "Edad y genero" in text
    assert menu.LABEL_AVAILABLE in text


# --- Dominio: genero, edad e IoU ---


def test_face_gender_values() -> None:
    assert FaceGender.FEMALE.value == "F"
    assert FaceGender.MALE.value == "M"
    assert FaceGender.UNKNOWN.value == "?"


@pytest.mark.parametrize("age", [MIN_ESTIMATED_AGE, MAX_ESTIMATED_AGE])
def test_face_attributes_accepts_age_limits(age: int) -> None:
    assert _face(_box(), age=age).age == age


@pytest.mark.parametrize("age", [-1, MAX_ESTIMATED_AGE + 1])
def test_face_attributes_rejects_age_out_of_range(age: int) -> None:
    with pytest.raises(ConfigError, match="edad estimada"):
        _face(_box(), age=age)


def test_intersection_over_union_of_identical_boxes_is_one() -> None:
    assert intersection_over_union(_box(), _box()) == pytest.approx(1.0)


def test_intersection_over_union_partial_overlap() -> None:
    first = _box(x_min=0.0, y_min=0.0, x_max=0.2, y_max=0.2)
    second = _box(x_min=0.1, y_min=0.1, x_max=0.3, y_max=0.3)

    assert intersection_over_union(first, second) == pytest.approx(1 / 7)


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (
            _box(x_min=0.0, y_min=0.0, x_max=0.2, y_max=0.2),
            _box(x_min=0.5, y_min=0.5, x_max=0.7, y_max=0.7),
        ),
        (
            _box(x_min=0.0, y_min=0.0, x_max=0.2, y_max=0.2),
            _box(x_min=0.2, y_min=0.0, x_max=0.4, y_max=0.2),
        ),
    ],
)
def test_intersection_over_union_zero_without_overlap(first: FaceBox, second: FaceBox) -> None:
    assert intersection_over_union(first, second) == 0.0


# --- Dominio: suavizador ---


@pytest.mark.parametrize(
    ("window", "iou_threshold", "max_misses", "match"),
    [
        (0, GENDER_AGE_IOU_THRESHOLD, GENDER_AGE_MAX_MISSES, "window"),
        (DEFAULT_GENDER_AGE_SMOOTHING_WINDOW, -0.1, GENDER_AGE_MAX_MISSES, "iou_threshold"),
        (DEFAULT_GENDER_AGE_SMOOTHING_WINDOW, 1.1, GENDER_AGE_MAX_MISSES, "iou_threshold"),
        (DEFAULT_GENDER_AGE_SMOOTHING_WINDOW, GENDER_AGE_IOU_THRESHOLD, 0, "max_misses"),
    ],
)
def test_smoother_rejects_invalid_parameters(
    window: int,
    iou_threshold: float,
    max_misses: int,
    match: str,
) -> None:
    with pytest.raises(ConfigError, match=match):
        AgeGenderSmoother(
            window=window,
            iou_threshold=iou_threshold,
            max_misses=max_misses,
        )


def test_smoother_empty_input_returns_empty_tuple() -> None:
    assert AgeGenderSmoother().update(()) == ()


def test_smoother_window_one_returns_raw_values() -> None:
    smoother = AgeGenderSmoother(window=1)
    box = _box()

    first = smoother.update((_face(box, age=10, gender=FaceGender.MALE),))
    second = smoother.update((_face(box, age=90, gender=FaceGender.FEMALE),))

    assert first[0].age == 10
    assert first[0].gender is FaceGender.MALE
    assert second[0].age == 90
    assert second[0].gender is FaceGender.FEMALE


def test_smoother_median_odd_and_even() -> None:
    odd = AgeGenderSmoother(window=3)
    box = _box()
    for age in (30, 10, 20):
        result = odd.update((_face(box, age=age),))
    assert result[0].age == 20

    even = AgeGenderSmoother(window=2)
    for age in (10, 20):
        result = even.update((_face(box, age=age),))
    assert result[0].age == 15


def test_smoother_gender_majority_vote() -> None:
    smoother = AgeGenderSmoother(window=3)
    box = _box()

    for gender in (FaceGender.MALE, FaceGender.MALE, FaceGender.FEMALE):
        result = smoother.update((_face(box, gender=gender),))

    assert result[0].gender is FaceGender.MALE


def test_smoother_gender_tie_uses_most_recent() -> None:
    smoother = AgeGenderSmoother(window=2)
    box = _box()

    result = smoother.update((_face(box, gender=FaceGender.MALE),))
    assert result[0].gender is FaceGender.MALE

    result = smoother.update((_face(box, gender=FaceGender.FEMALE),))
    assert result[0].gender is FaceGender.FEMALE

    result = smoother.update((_face(box, gender=FaceGender.FEMALE),))
    assert result[0].gender is FaceGender.FEMALE

    result = smoother.update((_face(box, gender=FaceGender.MALE),))
    assert result[0].gender is FaceGender.MALE


def test_smoother_tracks_faces_by_iou_and_keeps_order() -> None:
    smoother = AgeGenderSmoother(window=3)
    first = _box(x_min=0.10, y_min=0.10, x_max=0.30, y_max=0.30)
    second = _box(x_min=0.60, y_min=0.60, x_max=0.80, y_max=0.80)

    result = smoother.update((_face(first, age=10), _face(second, age=60)))
    assert [face.age for face in result] == [10, 60]

    shifted_first = _box(x_min=0.11, y_min=0.11, x_max=0.31, y_max=0.31)
    shifted_second = _box(x_min=0.61, y_min=0.61, x_max=0.81, y_max=0.81)
    result = smoother.update(
        (_face(shifted_first, age=20), _face(shifted_second, age=70)),
    )

    assert [face.age for face in result] == [15, 65]
    assert [face.box for face in result] == [shifted_first, shifted_second]


def test_smoother_creates_new_slot_for_unmatched_face() -> None:
    smoother = AgeGenderSmoother(window=3)
    smoother.update((_face(_box(x_min=0.1, y_min=0.1, x_max=0.2, y_max=0.2), age=10),))

    result = smoother.update(
        (_face(_box(x_min=0.7, y_min=0.7, x_max=0.9, y_max=0.9), age=80),),
    )

    assert result[0].age == 80


def test_smoother_prefers_highest_iou_slot() -> None:
    smoother = AgeGenderSmoother(window=3, iou_threshold=0.1)
    first = _box(x_min=0.10, y_min=0.10, x_max=0.30, y_max=0.30)
    second = _box(x_min=0.12, y_min=0.12, x_max=0.32, y_max=0.32)
    smoother.update((_face(first, age=10), _face(second, age=100)))

    probe = _box(x_min=0.105, y_min=0.105, x_max=0.305, y_max=0.305)
    result = smoother.update((_face(probe, age=20),))

    assert result[0].age == 15
    assert result[0].box == probe


def test_smoother_purges_slots_after_max_misses() -> None:
    smoother = AgeGenderSmoother(window=5, max_misses=1)
    box = _box()

    assert smoother.update((_face(box, age=10),))[0].age == 10
    assert smoother.update(()) == ()
    assert smoother.update(()) == ()

    # El slot purgado no conserva historial: la edad vuelve a ser cruda.
    assert smoother.update((_face(box, age=90),))[0].age == 90


def test_smoother_match_resets_misses() -> None:
    smoother = AgeGenderSmoother(window=5, max_misses=2)
    box = _box()

    smoother.update((_face(box, age=10),))
    smoother.update(())
    smoother.update((_face(box, age=20),))  # reencuentro: reinicia ausencias
    smoother.update(())
    smoother.update(())

    result = smoother.update((_face(box, age=30),))

    assert result[0].age == 20


# --- Overlay ---


def test_draw_gender_age_overlay_draws_faces_and_hud() -> None:
    image: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)

    draw_gender_age_overlay(image, faces=(_face(_box()),))

    assert image.shape == FRAME_SHAPE
    assert image.any()


def test_draw_gender_age_overlay_without_faces_still_draws_hud() -> None:
    image: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)

    draw_gender_age_overlay(image, faces=())

    assert image.any()


# --- Adaptador InsightFace con fachadas fake ---


class _FakeBox:
    def __init__(self, coords: tuple[float, float, float, float]) -> None:
        self._coords = coords

    def __len__(self) -> int:
        return len(self._coords)

    def __getitem__(self, index: int) -> float:
        return self._coords[index]


class _FakeFace:
    def __init__(
        self,
        bbox: tuple[float, float, float, float],
        det_score: float,
        *,
        gender: int | None = None,
        age: int | None = None,
    ) -> None:
        self.bbox = _FakeBox(bbox)
        self.det_score = det_score
        self.gender = gender
        self.age = age


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

    monkeypatch.setattr(attrs_module, "create_analysis", fake_create)


def test_attributes_facade_maps_and_clamps_attributes(monkeypatch: pytest.MonkeyPatch) -> None:
    analysis = _FakeAnalysis(
        [
            _FakeFace((10.0, 20.0, 60.0, 70.0), 0.9, gender=1, age=30),
            _FakeFace((-20.0, -10.0, 50.0, 60.0), 0.8, gender=0, age=5),
            _FakeFace((80.0, 90.0, 200.0, 300.0), 0.7, gender=None, age=200),
            _FakeFace((10.0, 10.0, 60.0, 60.0), 0.6, gender=7, age=-5),
        ]
    )
    _patch_analysis(monkeypatch, analysis)
    config = GenderAgeConfig()
    facade = attrs_module.InsightFaceAttributesFacade(config)
    facade.open()

    frame: NDArray[np.uint8] = np.zeros((100, 100, 3), dtype=np.uint8)
    attributes = facade.estimate(frame_bgr=frame, min_confidence=0.5)

    assert analysis.prepared == (0, (config.det_size, config.det_size))
    assert len(attributes) == 4
    assert attributes[0].box == _box(0.1, 0.2, 0.6, 0.7, confidence=0.9)
    assert attributes[0].age == 30
    assert attributes[0].gender is FaceGender.MALE
    assert attributes[1].box == _box(0.0, 0.0, 0.5, 0.6, confidence=0.8)
    assert attributes[1].gender is FaceGender.FEMALE
    assert attributes[2].box == _box(0.8, 0.9, 1.0, 1.0, confidence=0.7)
    assert attributes[2].age == MAX_ESTIMATED_AGE
    assert attributes[2].gender is FaceGender.UNKNOWN
    assert attributes[3].age == MIN_ESTIMATED_AGE
    assert attributes[3].gender is FaceGender.UNKNOWN


def test_attributes_facade_filters_weak_nan_age_and_degenerate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _FakeAnalysis(
        [
            _FakeFace((10.0, 10.0, 60.0, 60.0), 0.9, gender=1, age=30),
            _FakeFace((10.0, 10.0, 60.0, 60.0), 0.2, gender=1, age=30),
            _FakeFace((10.0, 10.0, 60.0, 60.0), float("nan"), gender=1, age=30),
            _FakeFace((10.0, 10.0, 60.0, 60.0), 0.9, gender=1, age=None),
            _FakeFace((10.0, 10.0, 10.0, 10.0), 0.9, gender=1, age=30),
        ]
    )
    _patch_analysis(monkeypatch, analysis)
    facade = attrs_module.InsightFaceAttributesFacade(GenderAgeConfig())
    facade.open()

    attributes = facade.estimate(
        frame_bgr=np.zeros((100, 100, 3), dtype=np.uint8),
        min_confidence=0.5,
    )

    assert len(attributes) == 1
    assert attributes[0].age == 30


def test_attributes_facade_requires_open(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_analysis(monkeypatch, _FakeAnalysis([]))
    facade = attrs_module.InsightFaceAttributesFacade(GenderAgeConfig())

    with pytest.raises(FaceAttributeError):
        facade.estimate(frame_bgr=np.zeros(FRAME_SHAPE, dtype=np.uint8), min_confidence=0.5)


def test_attributes_facade_rejects_double_open(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_analysis(monkeypatch, _FakeAnalysis([]))
    facade = attrs_module.InsightFaceAttributesFacade(GenderAgeConfig())
    facade.open()

    with pytest.raises(FaceAttributeError):
        facade.open()


def test_attributes_facade_wraps_analysis_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FailingAnalysis(_FakeAnalysis):
        def get(self, image_rgb: NDArray[np.uint8]) -> list[_FakeFace]:
            _ = image_rgb
            msg = "boom"
            raise RuntimeError(msg)

    _patch_analysis(monkeypatch, _FailingAnalysis([]))
    facade = attrs_module.InsightFaceAttributesFacade(GenderAgeConfig())
    facade.open()

    with pytest.raises(FaceAttributeError):
        facade.estimate(frame_bgr=np.zeros(FRAME_SHAPE, dtype=np.uint8), min_confidence=0.5)


def test_attributes_facade_open_wraps_model_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_create(*, model_path: str, modules: tuple[str, ...]) -> _FakeAnalysis:
        _ = (model_path, modules)
        msg = "sin modelo"
        raise ImportError(msg)

    monkeypatch.setattr(attrs_module, "create_analysis", failing_create)
    facade = attrs_module.InsightFaceAttributesFacade(GenderAgeConfig())

    with pytest.raises(FaceAttributeError):
        facade.open()


def test_attributes_facade_close_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_analysis(monkeypatch, _FakeAnalysis([]))
    facade = attrs_module.InsightFaceAttributesFacade(GenderAgeConfig())
    facade.open()

    facade.close()
    facade.close()

    with pytest.raises(FaceAttributeError):
        facade.estimate(frame_bgr=np.zeros(FRAME_SHAPE, dtype=np.uint8), min_confidence=0.5)


# --- Estimador con fachada fake ---


class _FakeFacade:
    def __init__(self, attributes: tuple[FaceAttributes, ...] = ()) -> None:
        self.attributes = attributes
        self.opened = 0
        self.closed = 0
        self.estimated = 0
        self.min_confidence: float | None = None

    def open(self) -> None:
        self.opened += 1

    def estimate(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        min_confidence: float,
    ) -> tuple[FaceAttributes, ...]:
        _ = frame_bgr
        self.estimated += 1
        self.min_confidence = min_confidence
        return self.attributes

    def close(self) -> None:
        self.closed += 1


def test_estimator_lifecycle_with_fake_facade() -> None:
    facade = _FakeFacade((_face(_box()),))
    created: list[_FakeFacade] = []

    def factory(_config: FaceAttributeEstimatorConfig) -> _FakeFacade:
        created.append(facade)
        return facade

    estimator = attrs_module.InsightFaceAttributeEstimator(
        GenderAgeConfig(), facade_factory=factory
    )
    assert created == []

    with pytest.raises(FaceAttributeError):
        estimator.estimate(_frame())

    with estimator as opened:
        result = opened.estimate(_frame())

    assert result == (_face(_box()),)
    assert created == [facade]
    assert facade.opened == 1
    assert facade.closed == 1
    assert facade.estimated == 1
    assert facade.min_confidence == GenderAgeConfig().min_confidence


def test_estimator_rejects_double_open() -> None:
    facade = _FakeFacade()
    estimator = attrs_module.InsightFaceAttributeEstimator(
        GenderAgeConfig(), facade_factory=lambda _config: facade
    )
    estimator.open()

    with pytest.raises(FaceAttributeError):
        estimator.open()

    assert facade.opened == 1


def test_estimator_open_propagates_facade_error() -> None:
    class _FailingFacade(_FakeFacade):
        def open(self) -> None:
            msg = "sin modelo"
            raise FaceAttributeError(msg)

    estimator = attrs_module.InsightFaceAttributeEstimator(
        GenderAgeConfig(), facade_factory=lambda _config: _FailingFacade()
    )

    with pytest.raises(FaceAttributeError, match="sin modelo"):
        estimator.open()


def test_estimator_close_without_open_is_safe() -> None:
    facade = _FakeFacade()
    estimator = attrs_module.InsightFaceAttributeEstimator(
        GenderAgeConfig(), facade_factory=lambda _config: facade
    )

    estimator.close()

    assert facade.closed == 0
    with pytest.raises(FaceAttributeError):
        estimator.estimate(_frame())


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
    def __init__(
        self,
        config: GenderAgeConfig,
        script: list[tuple[FaceAttributes, ...]],
    ) -> None:
        self.config = config
        self._script = script
        self.estimate_calls = 0

    def __enter__(self) -> "_FakeEstimatorCM":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def estimate(self, frame: Frame) -> tuple[FaceAttributes, ...]:
        _ = frame
        self.estimate_calls += 1
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
    script: list[tuple[FaceAttributes, ...]],
    app_config: AppConfig | None = None,
) -> _FakeEstimatorCM:
    resolved = app_config if app_config is not None else AppConfig()
    estimator = _FakeEstimatorCM(resolved.gender_age, script)
    _WORKERS.clear()

    monkeypatch.setattr(ga_module, "prepare_workspace", lambda path: path)
    monkeypatch.setattr(ga_module, "load_config", lambda path: resolved)  # noqa: ARG005
    monkeypatch.setattr(
        ga_module,
        "resolve_camera_config",
        lambda *, app_config, device_override: CameraConfig(),  # noqa: ARG005
    )
    monkeypatch.setattr(
        ga_module, "OpenCVCamera", lambda config: _DrivenSource(_FakeCamera(config, frames))
    )
    monkeypatch.setattr(ga_module, "LatestFrameSource", _FakeSourceContext)
    monkeypatch.setattr(ga_module, "LatestInferenceWorker", _FakeWorker)
    monkeypatch.setattr(
        ga_module,
        "InsightFaceAttributeEstimator",
        lambda config: estimator,  # noqa: ARG005
    )
    monkeypatch.setattr(cv2, "destroyAllWindows", lambda: None)
    return estimator


def _patch_window(monkeypatch: pytest.MonkeyPatch, keys: list[int]) -> list[str]:
    shown: list[str] = []
    pressed = iter(keys)

    monkeypatch.setattr(cv2, "namedWindow", lambda _name: None)
    monkeypatch.setattr(cv2, "setWindowProperty", lambda _name, _prop, _value: None)
    monkeypatch.setattr(cv2, "getWindowProperty", lambda _name, _prop: 1.0)
    monkeypatch.setattr(cv2, "imshow", lambda name, _data: shown.append(name))
    monkeypatch.setattr(cv2, "waitKey", lambda _delay: next(pressed))
    return shown


def test_runner_estimates_faces_headless(monkeypatch: pytest.MonkeyPatch) -> None:
    frames = [_frame(), _frame()]
    script: list[tuple[FaceAttributes, ...]] = [(_face(_box()),), ()]
    estimator = _patch_runner_env(monkeypatch, frames=frames, script=script)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=2)
    assert run_gender_age(request) == 0

    assert estimator.estimate_calls == 2


def test_runner_draws_overlay_in_place(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = Frame(data=_noisy_image(), timestamp=1.0)
    original = frame.data.copy()
    _patch_runner_env(monkeypatch, frames=[frame], script=[(_face(_box()),)])

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=1)
    assert run_gender_age(request) == 0

    assert not np.array_equal(frame.data, original)


@pytest.mark.parametrize("quit_key", [ord("q"), ESC_KEY])
def test_runner_stops_on_quit_key_and_returns_to_menu(
    monkeypatch: pytest.MonkeyPatch,
    quit_key: int,
) -> None:
    frames = [_frame(), _frame(), _frame()]
    script: list[tuple[FaceAttributes, ...]] = [(_face(_box()),)] * 3
    estimator = _patch_runner_env(monkeypatch, frames=frames, script=script)
    shown = _patch_window(monkeypatch, [0, quit_key])

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=True, max_frames=0)
    assert run_gender_age(request) == 0

    assert estimator.estimate_calls == 2
    assert shown == [ga_module.WINDOW_NAME, ga_module.WINDOW_NAME]


def test_runner_rejects_headless_without_frames() -> None:
    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=0)

    assert run_gender_age(request) == 1


def test_runner_returns_error_when_estimator_fails_to_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_runner_env(monkeypatch, frames=[_frame()], script=[])

    class _FailingEstimator:
        def __init__(self, config: GenderAgeConfig) -> None:
            self.config = config

        def __enter__(self) -> "_FailingEstimator":
            msg = "sin modelo"
            raise FaceAttributeError(msg)

        def __exit__(self, *exc_info: object) -> None:
            return None

    monkeypatch.setattr(ga_module, "InsightFaceAttributeEstimator", _FailingEstimator)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=1)
    assert run_gender_age(request) == 1
