"""Tests del adaptador de gestos MediaPipe con dobles de fachada y recognizer."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from recognizer.adapters import mediapipe_gesture_classifier as classifier_module
from recognizer.adapters.mediapipe_gesture_classifier import (
    MediaPipeGestureClassifier,
    MediaPipeTasksGestureFacade,
)
from recognizer.core.config import GestureConfig
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.gesture import (
    GESTURE_NONE,
    GESTURE_OPEN_PALM,
    GESTURE_VICTORY,
    GestureId,
    GestureRecognition,
)
from recognizer.core.domain.hand import HAND_LANDMARK_COUNT, Handedness, Point
from recognizer.core.errors import GestureClassifierError

FRAME_TIMESTAMP = 0.25
EXPECTED_TIMESTAMP_MS = 250
DETECT_TIMESTAMP_MS = 123
EMPTY_CONFIDENCE = 0.0


class FakeFacade:
    """Doble de GestureDetectorFacade que registra las llamadas recibidas."""

    def __init__(self, config: GestureConfig) -> None:
        self.config = config
        self.opened = False
        self.close_calls = 0
        self.timestamps_ms: list[int] = []
        self.frames: list[NDArray[np.uint8]] = []
        self.recognition = GestureRecognition(hands=(), detections=())

    def open(self) -> None:
        self.opened = True

    def detect(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        timestamp_ms: int,
    ) -> GestureRecognition:
        self.frames.append(frame_bgr)
        self.timestamps_ms.append(timestamp_ms)
        return self.recognition

    def close(self) -> None:
        self.close_calls += 1


@dataclass(frozen=True, slots=True)
class FakeLandmark:
    """Doble de NormalizedLandmark."""

    x: float
    y: float
    z: float


@dataclass(frozen=True, slots=True)
class FakeCategory:
    """Doble de Category (lateralidad o gesto)."""

    category_name: str
    score: float


@dataclass(frozen=True, slots=True)
class FakeResult:
    """Doble de GestureRecognizerResult."""

    handedness: Sequence[Sequence[FakeCategory]]
    hand_landmarks: Sequence[Sequence[FakeLandmark]]
    gestures: Sequence[Sequence[FakeCategory]]


class FakeRecognizer:
    """Doble de GestureRecognizer que devuelve un resultado fijo."""

    def __init__(self, result: FakeResult) -> None:
        self.result = result
        self.images: list[object] = []
        self.timestamps_ms: list[int] = []
        self.close_calls = 0

    def recognize_for_video(self, image: object, timestamp_ms: int) -> FakeResult:
        self.images.append(image)
        self.timestamps_ms.append(timestamp_ms)
        return self.result

    def close(self) -> None:
        self.close_calls += 1


class FailingRecognizer(FakeRecognizer):
    """Doble cuyo recognize_for_video falla como el runtime real de MediaPipe."""

    def recognize_for_video(self, image: object, timestamp_ms: int) -> FakeResult:
        del image, timestamp_ms
        raise RuntimeError("fallo de runtime simulado")


def _frame() -> Frame:
    data: NDArray[np.uint8] = np.zeros((4, 6, 3), dtype=np.uint8)
    return Frame(data=data, timestamp=FRAME_TIMESTAMP)


def _classifier_with_facade() -> tuple[MediaPipeGestureClassifier, FakeFacade]:
    facade = FakeFacade(GestureConfig())
    classifier = MediaPipeGestureClassifier(GestureConfig(), facade_factory=lambda _config: facade)
    return classifier, facade


def _landmarks(seed: float) -> tuple[FakeLandmark, ...]:
    return tuple(
        FakeLandmark(x=seed + index * 0.01, y=seed + index * 0.02, z=0.0)
        for index in range(HAND_LANDMARK_COUNT)
    )


def _open_facade(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    result: FakeResult,
    recognizer: FakeRecognizer | None = None,
    *,
    custom_labels: tuple[str, ...] = (),
) -> tuple[MediaPipeTasksGestureFacade, FakeRecognizer, object]:
    model_path = tmp_path / "gesture_recognizer.task"
    model_path.write_bytes(b"modelo falso")
    active_recognizer = FakeRecognizer(result) if recognizer is None else recognizer
    sentinel = object()

    def fake_create_recognizer(*, config: GestureConfig, model_path: Path) -> FakeRecognizer:
        del config, model_path
        return active_recognizer

    def fake_to_mp_image(frame_bgr: NDArray[np.uint8]) -> object:
        del frame_bgr
        return sentinel

    monkeypatch.setattr(classifier_module, "_create_recognizer", fake_create_recognizer)
    monkeypatch.setattr(classifier_module, "_to_mp_image", fake_to_mp_image)
    facade = MediaPipeTasksGestureFacade(
        GestureConfig(model_path=str(model_path), custom_labels=custom_labels)
    )
    facade.open()
    return facade, active_recognizer, sentinel


def test_open_creates_and_opens_facade_with_config() -> None:
    configs: list[GestureConfig] = []
    facades: list[FakeFacade] = []

    def factory(config: GestureConfig) -> FakeFacade:
        configs.append(config)
        facade = FakeFacade(config)
        facades.append(facade)
        return facade

    config = GestureConfig(max_hands=1)
    classifier = MediaPipeGestureClassifier(config, facade_factory=factory)
    classifier.open()

    assert configs == [config]
    assert len(facades) == 1
    assert facades[0].opened
    classifier.close()


def test_open_twice_raises() -> None:
    classifier, _ = _classifier_with_facade()
    classifier.open()
    with pytest.raises(GestureClassifierError, match="ya esta abierto"):
        classifier.open()
    classifier.close()


def test_classify_without_open_raises() -> None:
    classifier, _ = _classifier_with_facade()
    with pytest.raises(GestureClassifierError, match="no esta abierto"):
        classifier.classify(_frame())


def test_open_failure_propagates_and_leaves_classifier_closed() -> None:
    class FailingFacade:
        def open(self) -> None:
            raise GestureClassifierError("fallo simulado")

        def detect(
            self,
            *,
            frame_bgr: NDArray[np.uint8],
            timestamp_ms: int,
        ) -> GestureRecognition:
            del frame_bgr, timestamp_ms
            return GestureRecognition(hands=(), detections=())

        def close(self) -> None:
            pass

    classifier = MediaPipeGestureClassifier(
        GestureConfig(),
        facade_factory=lambda _config: FailingFacade(),
    )
    with pytest.raises(GestureClassifierError, match="fallo simulado"):
        classifier.open()
    with pytest.raises(GestureClassifierError, match="no esta abierto"):
        classifier.classify(_frame())


def test_classify_converts_timestamp_to_milliseconds() -> None:
    classifier, facade = _classifier_with_facade()
    frame = _frame()
    classifier.open()

    result = classifier.classify(frame)

    assert result == GestureRecognition(hands=(), detections=())
    assert facade.timestamps_ms == [EXPECTED_TIMESTAMP_MS]
    assert facade.frames == [frame.data]
    classifier.close()


def test_context_manager_opens_and_closes() -> None:
    classifier, facade = _classifier_with_facade()
    with classifier as entered:
        assert entered is classifier
        assert facade.opened

    assert facade.close_calls == 1


def test_close_is_idempotent() -> None:
    classifier, facade = _classifier_with_facade()
    classifier.open()
    classifier.close()
    classifier.close()

    assert facade.close_calls == 1


def test_close_without_open_is_noop() -> None:
    classifier, facade = _classifier_with_facade()
    classifier.close()

    assert facade.close_calls == 0


def test_facade_detect_maps_two_hands_gestures_and_lateralities(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = FakeResult(
        handedness=(
            (FakeCategory(category_name="Left", score=0.9),),
            (FakeCategory(category_name="Right", score=0.8),),
        ),
        hand_landmarks=(_landmarks(0.1), _landmarks(0.4)),
        gestures=(
            (FakeCategory(category_name="Victory", score=0.95),),
            (FakeCategory(category_name="Open_Palm", score=0.85),),
        ),
    )
    facade, recognizer, sentinel = _open_facade(monkeypatch, tmp_path, result)
    frame_bgr = np.zeros((4, 6, 3), dtype=np.uint8)

    recognition = facade.detect(frame_bgr=frame_bgr, timestamp_ms=DETECT_TIMESTAMP_MS)

    assert len(recognition.hands) == 2
    assert recognition.hands[0].handedness is Handedness.LEFT
    assert recognition.hands[0].confidence == pytest.approx(0.9)
    assert len(recognition.hands[0].points) == HAND_LANDMARK_COUNT
    assert recognition.hands[0].points[0] == Point(x=0.1, y=0.1, z=0.0)
    assert recognition.hands[1].handedness is Handedness.RIGHT
    assert recognition.hands[1].confidence == pytest.approx(0.8)
    assert recognition.hands[1].points[0] == Point(x=0.4, y=0.4, z=0.0)

    assert len(recognition.detections) == 2
    assert recognition.detections[0].name == GESTURE_VICTORY
    assert recognition.detections[0].confidence == pytest.approx(0.95)
    assert recognition.detections[0].handedness is Handedness.LEFT
    assert recognition.detections[1].name == GESTURE_OPEN_PALM
    assert recognition.detections[1].confidence == pytest.approx(0.85)
    assert recognition.detections[1].handedness is Handedness.RIGHT

    assert recognizer.images == [sentinel]
    assert recognizer.timestamps_ms == [DETECT_TIMESTAMP_MS]


def test_facade_detect_maps_unknown_gesture_label_to_none(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = FakeResult(
        handedness=((FakeCategory(category_name="Left", score=0.9),),),
        hand_landmarks=(_landmarks(0.0),),
        gestures=((FakeCategory(category_name="Dab", score=0.7),),),
    )
    facade, _, _ = _open_facade(monkeypatch, tmp_path, result)

    recognition = facade.detect(frame_bgr=np.zeros((4, 6, 3), dtype=np.uint8), timestamp_ms=0)

    assert len(recognition.hands) == 1
    assert recognition.hands[0].handedness is Handedness.LEFT
    assert len(recognition.detections) == 1
    assert recognition.detections[0].name is GESTURE_NONE
    assert recognition.detections[0].confidence == pytest.approx(0.7)
    assert recognition.detections[0].handedness is Handedness.LEFT


def test_facade_detect_maps_unknown_handedness_label(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = FakeResult(
        handedness=((FakeCategory(category_name="Palm", score=0.6),),),
        hand_landmarks=(_landmarks(0.0),),
        gestures=((FakeCategory(category_name="Victory", score=0.9),),),
    )
    facade, _, _ = _open_facade(monkeypatch, tmp_path, result)

    recognition = facade.detect(frame_bgr=np.zeros((4, 6, 3), dtype=np.uint8), timestamp_ms=0)

    assert recognition.hands[0].handedness is Handedness.UNKNOWN
    assert recognition.detections[0].handedness is Handedness.UNKNOWN


def test_facade_detect_without_categories_uses_unknown_and_none(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = FakeResult(handedness=(), hand_landmarks=(_landmarks(0.0),), gestures=())
    facade, _, _ = _open_facade(monkeypatch, tmp_path, result)

    recognition = facade.detect(frame_bgr=np.zeros((4, 6, 3), dtype=np.uint8), timestamp_ms=0)

    assert len(recognition.hands) == 1
    assert recognition.hands[0].handedness is Handedness.UNKNOWN
    assert recognition.hands[0].confidence == EMPTY_CONFIDENCE
    assert recognition.detections[0].name is GESTURE_NONE
    assert recognition.detections[0].confidence == EMPTY_CONFIDENCE
    assert recognition.detections[0].handedness is Handedness.UNKNOWN


def test_facade_detect_hand_without_matching_category_uses_unknown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = FakeResult(
        handedness=((FakeCategory(category_name="Left", score=0.9),),),
        hand_landmarks=(_landmarks(0.0), _landmarks(0.2)),
        gestures=((FakeCategory(category_name="Victory", score=0.9),),),
    )
    facade, _, _ = _open_facade(monkeypatch, tmp_path, result)

    recognition = facade.detect(frame_bgr=np.zeros((4, 6, 3), dtype=np.uint8), timestamp_ms=0)

    assert len(recognition.hands) == 2
    assert recognition.hands[0].handedness is Handedness.LEFT
    assert recognition.hands[1].handedness is Handedness.UNKNOWN
    assert recognition.hands[1].confidence == EMPTY_CONFIDENCE
    assert recognition.detections[1].name is GESTURE_NONE
    assert recognition.detections[1].confidence == EMPTY_CONFIDENCE


def test_facade_detect_wraps_runtime_error_in_gesture_classifier_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = FakeResult(handedness=(), hand_landmarks=(), gestures=())
    failing_recognizer = FailingRecognizer(result)
    facade, recognizer, _ = _open_facade(monkeypatch, tmp_path, result, failing_recognizer)
    assert recognizer is failing_recognizer

    with pytest.raises(
        GestureClassifierError,
        match="Fallo la clasificacion de gestos",
    ) as exc_info:
        facade.detect(frame_bgr=np.zeros((4, 6, 3), dtype=np.uint8), timestamp_ms=0)

    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_facade_open_with_missing_model_raises(tmp_path: Path) -> None:
    facade = MediaPipeTasksGestureFacade(
        GestureConfig(model_path=str(tmp_path / "missing.task")),
    )
    with pytest.raises(GestureClassifierError, match="No existe el modelo"):
        facade.open()


def test_facade_open_wraps_creation_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    model_path = tmp_path / "gesture_recognizer.task"
    model_path.write_bytes(b"modelo falso")

    def failing_create_recognizer(*, config: GestureConfig, model_path: Path) -> object:
        del config, model_path
        raise OSError("fallo de carga")

    monkeypatch.setattr(classifier_module, "_create_recognizer", failing_create_recognizer)
    facade = MediaPipeTasksGestureFacade(GestureConfig(model_path=str(model_path)))
    with pytest.raises(GestureClassifierError, match="No se pudo cargar"):
        facade.open()


def test_facade_open_twice_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = FakeResult(handedness=(), hand_landmarks=(), gestures=())
    facade, _, _ = _open_facade(monkeypatch, tmp_path, result)
    with pytest.raises(GestureClassifierError, match="ya esta abierto"):
        facade.open()


def test_facade_detect_without_open_raises(tmp_path: Path) -> None:
    facade = MediaPipeTasksGestureFacade(
        GestureConfig(model_path=str(tmp_path / "gesture.task")),
    )
    with pytest.raises(GestureClassifierError, match="llama a open"):
        facade.detect(frame_bgr=np.zeros((4, 6, 3), dtype=np.uint8), timestamp_ms=0)


def test_facade_close_releases_recognizer_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = FakeResult(handedness=(), hand_landmarks=(), gestures=())
    facade, recognizer, _ = _open_facade(monkeypatch, tmp_path, result)

    facade.close()
    facade.close()

    assert recognizer.close_calls == 1


def test_facade_close_without_open_is_noop(tmp_path: Path) -> None:
    facade = MediaPipeTasksGestureFacade(
        GestureConfig(model_path=str(tmp_path / "gesture.task")),
    )
    facade.close()


def test_facade_detect_maps_declared_custom_label(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = FakeResult(
        handedness=((FakeCategory(category_name="Left", score=0.9),),),
        hand_landmarks=(_landmarks(0.0),),
        gestures=((FakeCategory(category_name="Custom_Wave", score=0.7),),),
    )
    facade, _, _ = _open_facade(
        monkeypatch,
        tmp_path,
        result,
        custom_labels=("Custom_Wave",),
    )

    recognition = facade.detect(frame_bgr=np.zeros((4, 6, 3), dtype=np.uint8), timestamp_ms=0)

    assert recognition.detections[0].name == GestureId("Custom_Wave")
    assert recognition.detections[0].name.value == "Custom_Wave"
    assert recognition.detections[0].confidence == pytest.approx(0.7)


def test_facade_detect_maps_undeclared_label_to_none(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = FakeResult(
        handedness=((FakeCategory(category_name="Left", score=0.9),),),
        hand_landmarks=(_landmarks(0.0),),
        gestures=((FakeCategory(category_name="Surprise", score=0.7),),),
    )
    facade, _, _ = _open_facade(
        monkeypatch,
        tmp_path,
        result,
        custom_labels=("Custom_Wave",),
    )

    recognition = facade.detect(frame_bgr=np.zeros((4, 6, 3), dtype=np.uint8), timestamp_ms=0)

    assert recognition.detections[0].name is GESTURE_NONE
    assert recognition.detections[0].confidence == pytest.approx(0.7)
