"""Tests del adaptador de manos MediaPipe con dobles de fachada y landmarker."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from recognizer.adapters import mediapipe_hand_tracker as tracker_module
from recognizer.adapters.mediapipe_hand_tracker import (
    MediaPipeHandTracker,
    MediaPipeTasksFacade,
)
from recognizer.core.config import HandsConfig
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.hand import HAND_LANDMARK_COUNT, Handedness, HandLandmarks, Point
from recognizer.core.errors import HandTrackerError

FRAME_TIMESTAMP = 0.25
EXPECTED_TIMESTAMP_MS = 250
DETECT_TIMESTAMP_MS = 123
EMPTY_CONFIDENCE = 0.0


class FakeFacade:
    """Doble de HandDetectorFacade que registra las llamadas recibidas."""

    def __init__(self, config: HandsConfig) -> None:
        self.config = config
        self.opened = False
        self.close_calls = 0
        self.timestamps_ms: list[int] = []
        self.frames: list[NDArray[np.uint8]] = []
        self.hands: tuple[HandLandmarks, ...] = ()

    def open(self) -> None:
        self.opened = True

    def detect(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        timestamp_ms: int,
    ) -> tuple[HandLandmarks, ...]:
        self.frames.append(frame_bgr)
        self.timestamps_ms.append(timestamp_ms)
        return self.hands

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
    """Doble de Category (lateralidad)."""

    category_name: str
    score: float


@dataclass(frozen=True, slots=True)
class FakeResult:
    """Doble de HandLandmarkerResult."""

    handedness: Sequence[Sequence[FakeCategory]]
    hand_landmarks: Sequence[Sequence[FakeLandmark]]


class FakeLandmarker:
    """Doble de HandLandmarker que devuelve un resultado fijo."""

    def __init__(self, result: FakeResult) -> None:
        self.result = result
        self.images: list[object] = []
        self.timestamps_ms: list[int] = []
        self.close_calls = 0

    def detect_for_video(self, image: object, timestamp_ms: int) -> FakeResult:
        self.images.append(image)
        self.timestamps_ms.append(timestamp_ms)
        return self.result

    def close(self) -> None:
        self.close_calls += 1


class FailingLandmarker(FakeLandmarker):
    """Doble cuyo detect_for_video falla como el runtime real de MediaPipe."""

    def detect_for_video(self, image: object, timestamp_ms: int) -> FakeResult:
        del image, timestamp_ms
        raise RuntimeError("fallo de runtime simulado")


def _frame() -> Frame:
    data: NDArray[np.uint8] = np.zeros((4, 6, 3), dtype=np.uint8)
    return Frame(data=data, timestamp=FRAME_TIMESTAMP)


def _tracker_with_facade() -> tuple[MediaPipeHandTracker, FakeFacade]:
    facade = FakeFacade(HandsConfig())
    tracker = MediaPipeHandTracker(HandsConfig(), facade_factory=lambda _config: facade)
    return tracker, facade


def _landmarks(seed: float) -> tuple[FakeLandmark, ...]:
    return tuple(
        FakeLandmark(x=seed + index * 0.01, y=seed + index * 0.02, z=0.0)
        for index in range(HAND_LANDMARK_COUNT)
    )


def _open_facade(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    result: FakeResult,
    landmarker: FakeLandmarker | None = None,
) -> tuple[MediaPipeTasksFacade, FakeLandmarker, object]:
    model_path = tmp_path / "hand_landmarker.task"
    model_path.write_bytes(b"modelo falso")
    active_landmarker = FakeLandmarker(result) if landmarker is None else landmarker
    sentinel = object()

    def fake_create_landmarker(*, config: HandsConfig, model_path: Path) -> FakeLandmarker:
        del config, model_path
        return active_landmarker

    def fake_to_mp_image(frame_bgr: NDArray[np.uint8]) -> object:
        del frame_bgr
        return sentinel

    monkeypatch.setattr(tracker_module, "_create_landmarker", fake_create_landmarker)
    monkeypatch.setattr(tracker_module, "_to_mp_image", fake_to_mp_image)
    facade = MediaPipeTasksFacade(HandsConfig(model_path=str(model_path)))
    facade.open()
    return facade, active_landmarker, sentinel


def test_open_creates_and_opens_facade_with_config() -> None:
    configs: list[HandsConfig] = []
    facades: list[FakeFacade] = []

    def factory(config: HandsConfig) -> FakeFacade:
        configs.append(config)
        facade = FakeFacade(config)
        facades.append(facade)
        return facade

    config = HandsConfig(max_hands=1)
    tracker = MediaPipeHandTracker(config, facade_factory=factory)
    tracker.open()

    assert configs == [config]
    assert len(facades) == 1
    assert facades[0].opened
    tracker.close()


def test_open_twice_raises() -> None:
    tracker, _ = _tracker_with_facade()
    tracker.open()
    with pytest.raises(HandTrackerError, match="ya esta abierto"):
        tracker.open()
    tracker.close()


def test_detect_without_open_raises() -> None:
    tracker, _ = _tracker_with_facade()
    with pytest.raises(HandTrackerError, match="no esta abierto"):
        tracker.detect(_frame())


def test_open_failure_propagates_and_leaves_tracker_closed() -> None:
    class FailingFacade:
        def open(self) -> None:
            raise HandTrackerError("fallo simulado")

        def detect(
            self,
            *,
            frame_bgr: NDArray[np.uint8],
            timestamp_ms: int,
        ) -> tuple[HandLandmarks, ...]:
            del frame_bgr, timestamp_ms
            return ()

        def close(self) -> None:
            pass

    tracker = MediaPipeHandTracker(HandsConfig(), facade_factory=lambda _config: FailingFacade())
    with pytest.raises(HandTrackerError, match="fallo simulado"):
        tracker.open()
    with pytest.raises(HandTrackerError, match="no esta abierto"):
        tracker.detect(_frame())


def test_detect_converts_timestamp_to_milliseconds() -> None:
    tracker, facade = _tracker_with_facade()
    frame = _frame()
    tracker.open()

    result = tracker.detect(frame)

    assert result == ()
    assert facade.timestamps_ms == [EXPECTED_TIMESTAMP_MS]
    assert facade.frames == [frame.data]
    tracker.close()


def test_context_manager_opens_and_closes() -> None:
    tracker, facade = _tracker_with_facade()
    with tracker as entered:
        assert entered is tracker
        assert facade.opened

    assert facade.close_calls == 1


def test_close_is_idempotent() -> None:
    tracker, facade = _tracker_with_facade()
    tracker.open()
    tracker.close()
    tracker.close()

    assert facade.close_calls == 1


def test_close_without_open_is_noop() -> None:
    tracker, facade = _tracker_with_facade()
    tracker.close()

    assert facade.close_calls == 0


def test_facade_detect_maps_two_hands_and_lateralities(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = FakeResult(
        handedness=(
            (FakeCategory(category_name="Left", score=0.9),),
            (FakeCategory(category_name="Right", score=0.8),),
        ),
        hand_landmarks=(_landmarks(0.1), _landmarks(0.4)),
    )
    facade, landmarker, sentinel = _open_facade(monkeypatch, tmp_path, result)
    frame_bgr = np.zeros((4, 6, 3), dtype=np.uint8)

    hands = facade.detect(frame_bgr=frame_bgr, timestamp_ms=DETECT_TIMESTAMP_MS)

    assert len(hands) == 2
    assert hands[0].handedness is Handedness.LEFT
    assert hands[0].confidence == pytest.approx(0.9)
    assert len(hands[0].points) == HAND_LANDMARK_COUNT
    assert hands[0].points[0] == Point(x=0.1, y=0.1, z=0.0)
    assert hands[1].handedness is Handedness.RIGHT
    assert hands[1].confidence == pytest.approx(0.8)
    assert hands[1].points[0] == Point(x=0.4, y=0.4, z=0.0)
    assert landmarker.images == [sentinel]
    assert landmarker.timestamps_ms == [DETECT_TIMESTAMP_MS]


def test_facade_detect_maps_unknown_label(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = FakeResult(
        handedness=((FakeCategory(category_name="Palm", score=0.7),),),
        hand_landmarks=(_landmarks(0.0),),
    )
    facade, _, _ = _open_facade(monkeypatch, tmp_path, result)

    hands = facade.detect(frame_bgr=np.zeros((4, 6, 3), dtype=np.uint8), timestamp_ms=0)

    assert len(hands) == 1
    assert hands[0].handedness is Handedness.UNKNOWN
    assert hands[0].confidence == pytest.approx(0.7)


def test_facade_detect_without_categories_uses_unknown_and_zero_confidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = FakeResult(handedness=(), hand_landmarks=(_landmarks(0.0),))
    facade, _, _ = _open_facade(monkeypatch, tmp_path, result)

    hands = facade.detect(frame_bgr=np.zeros((4, 6, 3), dtype=np.uint8), timestamp_ms=0)

    assert len(hands) == 1
    assert hands[0].handedness is Handedness.UNKNOWN
    assert hands[0].confidence == EMPTY_CONFIDENCE


def test_facade_detect_hand_without_matching_category_uses_unknown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = FakeResult(
        handedness=((FakeCategory(category_name="Left", score=0.9),),),
        hand_landmarks=(_landmarks(0.0), _landmarks(0.2)),
    )
    facade, _, _ = _open_facade(monkeypatch, tmp_path, result)

    hands = facade.detect(frame_bgr=np.zeros((4, 6, 3), dtype=np.uint8), timestamp_ms=0)

    assert len(hands) == 2
    assert hands[0].handedness is Handedness.LEFT
    assert hands[1].handedness is Handedness.UNKNOWN
    assert hands[1].confidence == EMPTY_CONFIDENCE


def test_facade_detect_wraps_runtime_error_in_hand_tracker_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = FakeResult(handedness=(), hand_landmarks=())
    failing_landmarker = FailingLandmarker(result)
    facade, landmarker, _ = _open_facade(monkeypatch, tmp_path, result, failing_landmarker)
    assert landmarker is failing_landmarker

    with pytest.raises(HandTrackerError, match="Fallo la deteccion de manos") as exc_info:
        facade.detect(frame_bgr=np.zeros((4, 6, 3), dtype=np.uint8), timestamp_ms=0)

    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_facade_open_with_missing_model_raises(tmp_path: Path) -> None:
    facade = MediaPipeTasksFacade(HandsConfig(model_path=str(tmp_path / "missing.task")))
    with pytest.raises(HandTrackerError, match="No existe el modelo"):
        facade.open()


def test_facade_open_wraps_creation_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    model_path = tmp_path / "hand_landmarker.task"
    model_path.write_bytes(b"modelo falso")

    def failing_create_landmarker(*, config: HandsConfig, model_path: Path) -> object:
        del config, model_path
        raise OSError("fallo de carga")

    monkeypatch.setattr(tracker_module, "_create_landmarker", failing_create_landmarker)
    facade = MediaPipeTasksFacade(HandsConfig(model_path=str(model_path)))
    with pytest.raises(HandTrackerError, match="No se pudo cargar"):
        facade.open()


def test_facade_open_twice_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = FakeResult(handedness=(), hand_landmarks=())
    facade, _, _ = _open_facade(monkeypatch, tmp_path, result)
    with pytest.raises(HandTrackerError, match="ya esta abierto"):
        facade.open()


def test_facade_detect_without_open_raises(tmp_path: Path) -> None:
    facade = MediaPipeTasksFacade(HandsConfig(model_path=str(tmp_path / "hand.task")))
    with pytest.raises(HandTrackerError, match="llama a open"):
        facade.detect(frame_bgr=np.zeros((4, 6, 3), dtype=np.uint8), timestamp_ms=0)


def test_facade_close_releases_landmarker_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = FakeResult(handedness=(), hand_landmarks=())
    facade, landmarker, _ = _open_facade(monkeypatch, tmp_path, result)

    facade.close()
    facade.close()

    assert landmarker.close_calls == 1


def test_facade_close_without_open_is_noop(tmp_path: Path) -> None:
    facade = MediaPipeTasksFacade(HandsConfig(model_path=str(tmp_path / "hand.task")))
    facade.close()
