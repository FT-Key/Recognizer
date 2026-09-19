"""Tests del contador de personas (etapa 10c), sin hardware real.

Cubre el dominio de deteccion y tracking, el adaptador YOLO con fachada fake, la
configuracion y el runner con camara y detector fakes (bucle real).
"""

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray
from pydantic import ValidationError

from recognizer.adapters import ultralytics_detector as detector_module
from recognizer.adapters.ultralytics_detector import (
    UltralyticsDetector,
    UltralyticsDetectorFacade,
)
from recognizer.cli import menu
from recognizer.cli.apps import people_counter as pc_module
from recognizer.cli.apps.people_counter import run_people_counter
from recognizer.cli.menu import resolve_runner
from recognizer.core.config import (
    AppConfig,
    CameraConfig,
    CountingLineConfig,
    PeopleCounterConfig,
)
from recognizer.core.constants import (
    DEFAULT_PEOPLE_CONFIDENCE,
    DEFAULT_PEOPLE_MODEL_PATH,
    DEFAULT_TRACKER_CONFIG,
    PERSON_LABEL,
)
from recognizer.core.domain.app import AppAvailability, AppCatalog, AppId, AppRunRequest
from recognizer.core.domain.detection import (
    BoundingBox,
    Detection,
    count_by_label,
    count_people,
)
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.tracking import CountingLine, TrackedDetection
from recognizer.core.errors import ConfigError, DetectorError
from recognizer.core.ports.object_detector import DetectorConfig
from recognizer.core.ports.object_tracker import ObjectTracker

FRAME_SHAPE = (48, 64, 3)
REQUEST = AppRunRequest(config_path=Path("config.yaml"))


def _bbox(
    x_min: float = 0.1,
    y_min: float = 0.2,
    x_max: float = 0.4,
    y_max: float = 0.8,
) -> BoundingBox:
    return BoundingBox(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)


def _detection(label: str = PERSON_LABEL, confidence: float = 0.9) -> Detection:
    return Detection(label=label, confidence=confidence, bbox=_bbox())


def _bbox_at(*, y_min: float, y_max: float) -> BoundingBox:
    return BoundingBox(x_min=0.4, y_min=y_min, x_max=0.6, y_max=y_max)


def _tracked(
    track_id: int = 1,
    *,
    bbox: BoundingBox | None = None,
    label: str = PERSON_LABEL,
    confidence: float = 0.9,
) -> TrackedDetection:
    return TrackedDetection(
        track_id=track_id,
        detection=Detection(label=label, confidence=confidence, bbox=bbox or _bbox()),
    )


def _frame() -> Frame:
    data: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    return Frame(data=data, timestamp=1.0)


# --- Dominio: BoundingBox / Detection / conteo ---


def test_bbox_stores_normalized_coordinates_and_size() -> None:
    box = _bbox()

    assert (box.x_min, box.y_min, box.x_max, box.y_max) == (0.1, 0.2, 0.4, 0.8)
    assert box.width == pytest.approx(0.3)
    assert box.height == pytest.approx(0.6)


@pytest.mark.parametrize("field", ["x_min", "y_min", "x_max", "y_max"])
@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_bbox_rejects_out_of_range_coordinates(field: str, value: float) -> None:
    coords = {"x_min": 0.1, "y_min": 0.2, "x_max": 0.4, "y_max": 0.8}
    coords[field] = value

    with pytest.raises(ConfigError, match="0 <="):
        BoundingBox(**coords)


@pytest.mark.parametrize(
    "coords",
    [
        {"x_min": 0.5, "y_min": 0.2, "x_max": 0.5, "y_max": 0.8},
        {"x_min": 0.6, "y_min": 0.2, "x_max": 0.4, "y_max": 0.8},
        {"x_min": 0.1, "y_min": 0.7, "x_max": 0.4, "y_max": 0.7},
        {"x_min": 0.1, "y_min": 0.8, "x_max": 0.4, "y_max": 0.2},
    ],
)
def test_bbox_rejects_degenerate_boxes(coords: dict[str, float]) -> None:
    with pytest.raises(ConfigError, match=r"x_min < x_max|y_min < y_max"):
        BoundingBox(**coords)


def test_detection_rejects_empty_label() -> None:
    with pytest.raises(ConfigError, match="etiqueta no vacia"):
        Detection(label="", confidence=0.9, bbox=_bbox())


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_detection_rejects_out_of_range_confidence(confidence: float) -> None:
    with pytest.raises(ConfigError, match="confianza"):
        Detection(label=PERSON_LABEL, confidence=confidence, bbox=_bbox())


def test_count_by_label_matches_exact_label() -> None:
    detections = (
        _detection(label=PERSON_LABEL),
        _detection(label=PERSON_LABEL),
        _detection(label="car"),
    )

    assert count_by_label(detections, label=PERSON_LABEL) == 2
    assert count_by_label(detections, label="car") == 1
    assert count_by_label(detections, label="Person") == 0
    assert count_by_label((), label=PERSON_LABEL) == 0


def test_count_people_uses_person_label_by_default() -> None:
    detections = (_detection(), _detection(label="car"))

    assert count_people(detections) == 1
    assert count_people(detections, label="car") == 1


# --- Configuracion ---


def test_people_counter_config_defaults() -> None:
    config = PeopleCounterConfig()

    assert config.model_path == DEFAULT_PEOPLE_MODEL_PATH
    assert config.min_confidence == DEFAULT_PEOPLE_CONFIDENCE
    assert config.target_label == PERSON_LABEL


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_people_counter_config_rejects_bad_confidence(confidence: float) -> None:
    with pytest.raises(ValidationError):
        PeopleCounterConfig(min_confidence=confidence)


def test_people_counter_config_rejects_empty_strings() -> None:
    with pytest.raises(ValidationError):
        PeopleCounterConfig(model_path="")
    with pytest.raises(ValidationError):
        PeopleCounterConfig(target_label="")


def test_app_config_includes_people_counter() -> None:
    config = AppConfig()

    assert config.people_counter == PeopleCounterConfig()
    parsed = AppConfig.model_validate(
        {"people_counter": {"model_path": "models/x.pt", "min_confidence": 0.7}}
    )
    assert parsed.people_counter.model_path == "models/x.pt"
    assert parsed.people_counter.min_confidence == 0.7


# --- Adaptador: UltralyticsDetector con fachada fake ---


class FakeFacade:
    """Fachada fake con guion de detecciones y registro de llamadas."""

    def __init__(self, config: DetectorConfig) -> None:
        self.config = config
        self.detections: tuple[Detection, ...] = ()
        self.tracked: tuple[TrackedDetection, ...] = ()
        self.open_calls = 0
        self.close_calls = 0
        self.seen_confidences: list[float] = []

    def open(self) -> None:
        self.open_calls += 1

    def detect(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        min_confidence: float,
    ) -> tuple[Detection, ...]:
        _ = frame_bgr
        self.seen_confidences.append(min_confidence)
        return self.detections

    def track(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        min_confidence: float,
    ) -> tuple[TrackedDetection, ...]:
        _ = frame_bgr
        self.seen_confidences.append(min_confidence)
        return self.tracked

    def close(self) -> None:
        self.close_calls += 1


def _detector_with_fake(
    script: tuple[Detection, ...],
    tracked: tuple[TrackedDetection, ...] = (),
) -> tuple[UltralyticsDetector, FakeFacade]:
    fake: FakeFacade | None = None

    def factory(config: DetectorConfig) -> FakeFacade:
        nonlocal fake
        fake = FakeFacade(config)
        fake.detections = script
        fake.tracked = tracked
        return fake

    detector = UltralyticsDetector(PeopleCounterConfig(), facade_factory=factory)
    assert fake is None  # la fabrica solo se usa al abrir
    detector.open()
    assert fake is not None
    return detector, fake


def test_detector_delegates_to_facade_with_config_confidence() -> None:
    script = (_detection(), _detection(label="car"))
    detector, fake = _detector_with_fake(script)

    found = detector.detect(_frame())

    assert found == script
    assert fake.open_calls == 1
    assert fake.seen_confidences == [DEFAULT_PEOPLE_CONFIDENCE]


def test_detector_open_twice_raises() -> None:
    detector, _ = _detector_with_fake(())

    with pytest.raises(DetectorError, match="ya esta abierto"):
        detector.open()


def test_detector_track_delegates_to_facade_with_config_confidence() -> None:
    script = (_tracked(1), _tracked(2, label="car"))
    detector, fake = _detector_with_fake((), tracked=script)

    found = detector.track(_frame())

    assert found == script
    assert fake.open_calls == 1
    assert fake.seen_confidences == [DEFAULT_PEOPLE_CONFIDENCE]


def test_detector_track_without_open_raises() -> None:
    detector = UltralyticsDetector(PeopleCounterConfig(), facade_factory=FakeFacade)

    with pytest.raises(DetectorError, match="no esta abierto"):
        detector.track(_frame())


def test_ultralytics_detector_satisfies_object_tracker_protocol() -> None:
    tracker: ObjectTracker = UltralyticsDetector(PeopleCounterConfig())

    with pytest.raises(DetectorError, match="no esta abierto"):
        tracker.track(_frame())


def test_detector_detect_without_open_raises() -> None:
    detector = UltralyticsDetector(PeopleCounterConfig(), facade_factory=FakeFacade)

    with pytest.raises(DetectorError, match="no esta abierto"):
        detector.detect(_frame())


def test_detector_close_is_idempotent_and_releases_facade() -> None:
    detector, fake = _detector_with_fake(())

    detector.close()
    detector.close()

    assert fake.close_calls == 1
    with pytest.raises(DetectorError, match="no esta abierto"):
        detector.detect(_frame())


def test_detector_context_manager_opens_and_closes() -> None:
    seen: list[FakeFacade] = []

    def factory(config: DetectorConfig) -> FakeFacade:
        fake = FakeFacade(config)
        seen.append(fake)
        return fake

    with UltralyticsDetector(PeopleCounterConfig(), facade_factory=factory):
        pass

    assert len(seen) == 1
    assert seen[0].open_calls == 1
    assert seen[0].close_calls == 1


# --- Fachada real: mapeo de resultados y errores ---


class _FakeScalar:
    def __init__(self, value: float) -> None:
        self._value = value

    def __float__(self) -> float:
        return self._value

    def __int__(self) -> int:
        return int(self._value)


class _FakeRow:
    def __init__(
        self,
        coords: tuple[float, float, float, float],
        confidence: float,
        cls: int,
        track_id: int | None = None,
    ) -> None:
        self._coords = coords
        self._confidence = confidence
        self._cls = cls
        self._track_id = track_id

    @property
    def xyxyn(self) -> list[list[_FakeScalar]]:
        return [[_FakeScalar(value) for value in self._coords]]

    @property
    def conf(self) -> list[_FakeScalar]:
        return [_FakeScalar(self._confidence)]

    @property
    def cls(self) -> list[_FakeScalar]:
        return [_FakeScalar(float(self._cls))]

    @property
    def id(self) -> list[_FakeScalar] | None:
        if self._track_id is None:
            return None
        return [_FakeScalar(float(self._track_id))]


class _FakeBoxes:
    def __init__(self, rows: list[_FakeRow]) -> None:
        self._rows = rows

    def __len__(self) -> int:
        return len(self._rows)

    def __getitem__(self, index: int) -> _FakeRow:
        return self._rows[index]


class _FakeResult:
    def __init__(self, boxes: _FakeBoxes | None, names: dict[int, str]) -> None:
        self._boxes = boxes
        self._names = names

    @property
    def boxes(self) -> _FakeBoxes | None:
        return self._boxes

    @property
    def names(self) -> dict[int, str]:
        return self._names


class _FakeModel:
    def __init__(self, results: list[_FakeResult]) -> None:
        self._results = results
        self.seen_conf: list[float] = []
        self.seen_track: list[tuple[float, bool, str]] = []

    def predict(self, source: object, *, conf: float, verbose: bool) -> list[_FakeResult]:
        _ = (source, verbose)
        self.seen_conf.append(conf)
        return self._results

    def track(
        self,
        source: object,
        *,
        conf: float,
        persist: bool,
        verbose: bool,
        tracker: str,
    ) -> list[_FakeResult]:
        _ = (source, verbose)
        self.seen_conf.append(conf)
        self.seen_track.append((conf, persist, tracker))
        return self._results


def _facade_with_model(
    monkeypatch: pytest.MonkeyPatch,
    results: list[_FakeResult],
) -> tuple[UltralyticsDetectorFacade, _FakeModel]:
    config = PeopleCounterConfig()
    model = _FakeModel(results)
    monkeypatch.setattr(detector_module, "_create_model", lambda *, model_path: model)  # noqa: ARG005
    facade = UltralyticsDetectorFacade(config)
    facade.open()
    return facade, model


def test_facade_maps_results_filters_confidence_and_unknown_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    names = {0: PERSON_LABEL, 1: "car"}
    results = [
        _FakeResult(
            _FakeBoxes(
                [
                    _FakeRow((0.1, 0.2, 0.4, 0.8), 0.9, 0),
                    _FakeRow((0.0, 0.0, 0.5, 0.5), 0.1, 0),
                    _FakeRow((0.0, 0.0, 0.5, 0.5), 0.9, 7),
                    _FakeRow((0.5, 0.5, 0.9, 0.9), 0.7, 1),
                ]
            ),
            names,
        ),
        _FakeResult(None, names),
    ]
    facade, model = _facade_with_model(monkeypatch, results)

    found = facade.detect(frame_bgr=_frame().data, min_confidence=0.5)

    assert [(item.label, item.confidence) for item in found] == [(PERSON_LABEL, 0.9), ("car", 0.7)]
    assert model.seen_conf == [0.5]


def test_facade_detect_without_open_raises() -> None:
    facade = UltralyticsDetectorFacade(PeopleCounterConfig())

    with pytest.raises(DetectorError, match="no esta abierto"):
        facade.detect(frame_bgr=_frame().data, min_confidence=0.5)


def test_facade_track_maps_ids_filters_rows_and_passes_kwargs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    names = {0: PERSON_LABEL, 1: "car"}
    results = [
        _FakeResult(
            _FakeBoxes(
                [
                    _FakeRow((0.1, 0.2, 0.4, 0.8), 0.9, 0, track_id=3),
                    _FakeRow((0.0, 0.0, 0.5, 0.5), 0.9, 0),
                    _FakeRow((0.0, 0.0, 0.5, 0.5), 0.1, 0, track_id=4),
                    _FakeRow((0.0, 0.0, 0.5, 0.5), 0.9, 7, track_id=5),
                    _FakeRow((0.5, 0.5, 0.9, 0.9), 0.7, 1, track_id=6),
                ]
            ),
            names,
        ),
        _FakeResult(None, names),
    ]
    facade, model = _facade_with_model(monkeypatch, results)

    found = facade.track(frame_bgr=_frame().data, min_confidence=0.5)

    assert [(item.track_id, item.label, item.confidence) for item in found] == [
        (3, PERSON_LABEL, 0.9),
        (6, "car", 0.7),
    ]
    assert model.seen_conf == [0.5]
    assert model.seen_track == [(0.5, True, DEFAULT_TRACKER_CONFIG)]


def test_facade_track_without_open_raises() -> None:
    facade = UltralyticsDetectorFacade(PeopleCounterConfig())

    with pytest.raises(DetectorError, match="no esta abierto"):
        facade.track(frame_bgr=_frame().data, min_confidence=0.5)


def test_facade_track_failure_wraps_detector_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BrokenTrackModel(_FakeModel):
        def track(
            self,
            source: object,
            *,
            conf: float,
            persist: bool,
            verbose: bool,
            tracker: str,
        ) -> list[_FakeResult]:
            _ = (source, conf, persist, verbose, tracker)
            raise RuntimeError(" exploto el tracker")

    monkeypatch.setattr(
        detector_module,
        "_create_model",
        lambda *, model_path: _BrokenTrackModel([]),  # noqa: ARG005
    )
    facade = UltralyticsDetectorFacade(PeopleCounterConfig())
    facade.open()

    with pytest.raises(DetectorError, match="Fallo el tracking"):
        facade.track(frame_bgr=_frame().data, min_confidence=0.5)


def test_facade_open_twice_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    facade, _ = _facade_with_model(monkeypatch, [])

    with pytest.raises(DetectorError, match="ya esta abierto"):
        facade.open()


def test_facade_open_failure_wraps_detector_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing(*, model_path: str) -> _FakeModel:
        raise OSError(f"falta {model_path}")

    monkeypatch.setattr(detector_module, "_create_model", failing)

    with pytest.raises(DetectorError, match="No se pudo cargar"):
        UltralyticsDetectorFacade(PeopleCounterConfig()).open()


def test_facade_predict_failure_wraps_detector_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BrokenModel(_FakeModel):
        def predict(self, source: object, *, conf: float, verbose: bool) -> list[_FakeResult]:
            _ = (source, conf, verbose)
            raise RuntimeError(" exploto el runtime")

    monkeypatch.setattr(detector_module, "_create_model", lambda *, model_path: _BrokenModel([]))  # noqa: ARG005
    facade = UltralyticsDetectorFacade(PeopleCounterConfig())
    facade.open()

    with pytest.raises(DetectorError, match="Fallo la deteccion"):
        facade.detect(frame_bgr=_frame().data, min_confidence=0.5)


def test_facade_close_is_idempotent() -> None:
    facade = UltralyticsDetectorFacade(PeopleCounterConfig())

    facade.close()
    facade.close()


# --- Menu y catalogo ---


def test_resolve_people_counter_runner_is_lazy() -> None:
    before = set(sys.modules)

    assert resolve_runner(AppId.PEOPLE_COUNTER) is run_people_counter

    added = set(sys.modules) - before
    assert "ultralytics" not in added
    assert "torch" not in added


def test_people_counter_catalog_entry_is_available() -> None:
    catalog = AppCatalog()

    info = catalog.require(AppId.PEOPLE_COUNTER)
    assert info.implemented is True
    assert catalog.availability(AppId.PEOPLE_COUNTER, enabled={}) is AppAvailability.AVAILABLE
    assert (
        catalog.availability(AppId.PEOPLE_COUNTER, enabled={AppId.PEOPLE_COUNTER: False})
        is AppAvailability.DISABLED
    )


def test_menu_renders_people_counter_as_available() -> None:
    from recognizer.core.config import AppsConfig

    text = menu.render_catalog(AppCatalog(), AppsConfig())

    assert "  2) Contador de personas" in text
    assert menu.LABEL_AVAILABLE in text.splitlines()[5]


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
        config: PeopleCounterConfig,
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
    camera_holder: list[_FakeCamera] = []
    detector = _FakeDetectorCM(resolved.people_counter, script)

    def camera_factory(config: CameraConfig) -> _FakeCamera:
        camera = _FakeCamera(config, frames)
        camera_holder.append(camera)
        return camera

    monkeypatch.setattr(pc_module, "prepare_workspace", lambda path: path)
    monkeypatch.setattr(pc_module, "load_config", lambda path: resolved)  # noqa: ARG005
    monkeypatch.setattr(
        pc_module,
        "resolve_camera_config",
        lambda *, app_config, device_override: CameraConfig(),  # noqa: ARG005
    )
    monkeypatch.setattr(pc_module, "OpenCVCamera", camera_factory)
    monkeypatch.setattr(pc_module, "UltralyticsDetector", lambda config: detector)  # noqa: ARG005
    monkeypatch.setattr(cv2, "destroyAllWindows", lambda: None)
    return detector


def _app_config_with_line(*, enabled: bool, confirm_frames: int = 1) -> AppConfig:
    return AppConfig(
        people_counter=PeopleCounterConfig(
            line=CountingLineConfig(enabled=enabled, confirm_frames=confirm_frames)
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

    monkeypatch.setattr(pc_module, "draw_people_overlay", fake_draw)
    return calls


def test_runner_counts_and_draws_hud_headless(monkeypatch: pytest.MonkeyPatch) -> None:
    frames = [_frame(), _frame()]
    script: list[tuple[TrackedDetection, ...]] = [
        (_tracked(1), _tracked(2, confidence=0.8)),
        (_tracked(3, label="car"),),
    ]
    detector = _patch_runner_env(monkeypatch, frames=frames, script=script)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=2)
    assert run_people_counter(request) == 0

    assert detector.track_calls == 2
    for frame in frames:
        assert np.any(frame.data != 0)


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
    assert run_people_counter(request) == 0

    assert detector.track_calls == 2
    assert shown == [pc_module.WINDOW_NAME, pc_module.WINDOW_NAME]


def test_runner_with_line_disabled_keeps_counts_at_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    script: list[tuple[TrackedDetection, ...]] = [
        (_tracked(1, bbox=_bbox_at(y_min=0.1, y_max=0.3)),),
        (_tracked(1, bbox=_bbox_at(y_min=0.7, y_max=0.9)),),
    ]
    _patch_runner_env(
        monkeypatch,
        frames=[_frame(), _frame()],
        script=script,
        app_config=_app_config_with_line(enabled=False),
    )
    calls = _record_overlay(monkeypatch)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=2)
    assert run_people_counter(request) == 0

    assert calls == [(1, 0, 0), (1, 0, 0)]


def test_runner_with_line_enabled_accumulates_crossing_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script: list[tuple[TrackedDetection, ...]] = [
        (_tracked(1, bbox=_bbox_at(y_min=0.1, y_max=0.3)),),
        (_tracked(1, bbox=_bbox_at(y_min=0.7, y_max=0.9)),),
    ]
    _patch_runner_env(
        monkeypatch,
        frames=[_frame(), _frame()],
        script=script,
        app_config=_app_config_with_line(enabled=True, confirm_frames=1),
    )
    calls = _record_overlay(monkeypatch)

    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=2)
    assert run_people_counter(request) == 0

    assert calls == [(1, 0, 0), (1, 1, 0)]


def test_runner_rejects_headless_without_frames() -> None:
    request = AppRunRequest(config_path=Path("config.yaml"), show_window=False, max_frames=0)

    assert run_people_counter(request) == 1
