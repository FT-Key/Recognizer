"""Tests del adaptador Ultralytics pose, con fachadas y resultados fake.

No importa ultralytics/torch reales: el modelo y los resultados se sustituyen por
dobles que exponen el subconjunto de la API que usa el adaptador.
"""

import numpy as np
import pytest
from numpy.typing import NDArray

from recognizer.adapters import ultralytics_pose as pose_module
from recognizer.adapters.ultralytics_pose import (
    UltralyticsPoseEstimator,
    UltralyticsPoseFacade,
    _clamp01,
    _clamp_confidence,
    _map_result,
    _map_results,
    _pose_confidence,
)
from recognizer.core.config import PostureConfig
from recognizer.core.domain.detection import MAX_CONFIDENCE
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.pose import COCO_KEYPOINT_ORDER, Pose
from recognizer.core.errors import PoseEstimatorError
from recognizer.core.ports.pose_estimator import PoseEstimator, PoseEstimatorConfig

FRAME_SHAPE = (48, 64, 3)
KEYPOINT_COUNT = len(COCO_KEYPOINT_ORDER)


def _frame() -> Frame:
    data: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    return Frame(data=data, timestamp=1.0)


def _uniform_xyn(count: int = KEYPOINT_COUNT) -> NDArray[np.float64]:
    return np.full((1, count, 2), (0.5, 0.5), dtype=np.float64)


class _FakeKeypoints:
    """Doble de `Results.keypoints` con `xyn` (N,K,2) y `conf` (N,K) o None."""

    def __init__(
        self,
        xyn: NDArray[np.float64],
        conf: NDArray[np.float64] | None,
    ) -> None:
        self._xyn = xyn
        self._conf = conf

    @property
    def xyn(self) -> NDArray[np.float64]:
        return self._xyn

    @property
    def conf(self) -> NDArray[np.float64] | None:
        return self._conf

    def __len__(self) -> int:
        return int(self._xyn.shape[0])


class _FakeResult:
    """Doble de `Results` para pose."""

    def __init__(self, keypoints: _FakeKeypoints | None) -> None:
        self._keypoints = keypoints

    @property
    def keypoints(self) -> _FakeKeypoints | None:
        return self._keypoints


class _FakeModel:
    """Doble de `ultralytics.YOLO` para pose."""

    def __init__(self, results: list[_FakeResult]) -> None:
        self._results = results
        self.seen_conf: list[float] = []

    def predict(self, source: object, *, conf: float, verbose: bool) -> list[_FakeResult]:
        _ = (source, verbose)
        self.seen_conf.append(conf)
        return self._results


# --- Helpers puros de mapeo ---


def test_clamp_helpers_recortan_al_rango() -> None:
    assert _clamp01(-0.3) == 0.0
    assert _clamp01(0.4) == 0.4
    assert _clamp01(1.7) == 1.0
    assert _clamp_confidence(-0.3) == 0.0
    assert _clamp_confidence(0.4) == 0.4
    assert _clamp_confidence(1.7) == 1.0


def test_pose_confidence_returns_average() -> None:
    keypoints = _FakeKeypoints(_uniform_xyn(), np.full((1, KEYPOINT_COUNT), 0.8))

    assert _pose_confidence(keypoints=keypoints, index=0) == pytest.approx(0.8)


def test_pose_confidence_defaults_to_max_without_confidences() -> None:
    keypoints = _FakeKeypoints(_uniform_xyn(), None)

    assert _pose_confidence(keypoints=keypoints, index=0) == MAX_CONFIDENCE


def test_pose_confidence_defaults_to_max_for_empty_vector() -> None:
    keypoints = _FakeKeypoints(np.zeros((1, 0, 2)), np.zeros((1, 0)))

    assert _pose_confidence(keypoints=keypoints, index=0) == MAX_CONFIDENCE


def test_map_result_maps_coco_names_and_confidence() -> None:
    keypoints = _FakeKeypoints(_uniform_xyn(), np.full((1, KEYPOINT_COUNT), 0.8))

    poses = _map_result(result=_FakeResult(keypoints), min_confidence=0.5)

    assert len(poses) == 1
    pose = poses[0]
    assert pose.confidence == pytest.approx(0.8)
    assert tuple(keypoint.name for keypoint in pose.keypoints) == COCO_KEYPOINT_ORDER
    assert all(keypoint.confidence == pytest.approx(0.8) for keypoint in pose.keypoints)


def test_map_result_without_confidences_uses_max() -> None:
    keypoints = _FakeKeypoints(_uniform_xyn(), None)

    poses = _map_result(result=_FakeResult(keypoints), min_confidence=0.5)

    assert poses[0].confidence == MAX_CONFIDENCE
    assert all(keypoint.confidence == MAX_CONFIDENCE for keypoint in poses[0].keypoints)


def test_map_result_filters_below_min_confidence() -> None:
    keypoints = _FakeKeypoints(_uniform_xyn(), np.full((1, KEYPOINT_COUNT), 0.4))

    assert _map_result(result=_FakeResult(keypoints), min_confidence=0.5) == ()


def test_map_result_clamps_coordinates_and_confidences() -> None:
    xyn = np.array([[[-0.2, 1.5], [0.5, 0.5]]], dtype=np.float64)
    conf = np.array([[-0.5, 1.5]], dtype=np.float64)
    keypoints = _FakeKeypoints(xyn, conf)

    poses = _map_result(result=_FakeResult(keypoints), min_confidence=0.5)

    assert poses[0].confidence == pytest.approx(0.5)
    first, second = poses[0].keypoints
    assert (first.x, first.y, first.confidence) == (0.0, 1.0, 0.0)
    assert (second.x, second.y, second.confidence) == (0.5, 0.5, 1.0)


def test_map_result_without_keypoints_returns_empty() -> None:
    assert _map_result(result=_FakeResult(None), min_confidence=0.5) == ()


def test_map_result_with_no_people_returns_empty() -> None:
    keypoints = _FakeKeypoints(np.zeros((0, KEYPOINT_COUNT, 2)), np.zeros((0, KEYPOINT_COUNT)))

    assert _map_result(result=_FakeResult(keypoints), min_confidence=0.5) == ()


def test_map_result_with_fewer_keypoints_maps_available_ones() -> None:
    keypoints = _FakeKeypoints(_uniform_xyn(count=3), np.full((1, 3), 0.9))

    poses = _map_result(result=_FakeResult(keypoints), min_confidence=0.5)

    assert len(poses[0].keypoints) == 3
    assert poses[0].keypoints[0].name is COCO_KEYPOINT_ORDER[0]


def test_map_results_concatenates_every_result() -> None:
    keypoints = _FakeKeypoints(_uniform_xyn(), np.full((1, KEYPOINT_COUNT), 0.9))
    results: list[pose_module._PoseResultLike] = [
        _FakeResult(keypoints),
        _FakeResult(None),
        _FakeResult(keypoints),
    ]

    poses = _map_results(results=results, min_confidence=0.5)

    assert len(poses) == 2


# --- Fachada real con modelo fake ---


def _facade_with_model(
    monkeypatch: pytest.MonkeyPatch,
    results: list[_FakeResult],
) -> tuple[UltralyticsPoseFacade, _FakeModel]:
    config = PostureConfig()
    model = _FakeModel(results)
    monkeypatch.setattr(pose_module, "_create_pose_model", lambda *, model_path: model)  # noqa: ARG005
    facade = UltralyticsPoseFacade(config)
    facade.open()
    return facade, model


def test_facade_estimate_maps_results_and_passes_conf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keypoints = _FakeKeypoints(_uniform_xyn(), np.full((1, KEYPOINT_COUNT), 0.9))
    facade, model = _facade_with_model(monkeypatch, [_FakeResult(keypoints)])

    poses = facade.estimate(frame_bgr=_frame().data, min_confidence=0.5)

    assert len(poses) == 1
    assert model.seen_conf == [0.5]


def test_facade_estimate_without_open_raises() -> None:
    facade = UltralyticsPoseFacade(PostureConfig())

    with pytest.raises(PoseEstimatorError, match="no esta abierto"):
        facade.estimate(frame_bgr=_frame().data, min_confidence=0.5)


def test_facade_open_twice_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    facade, _ = _facade_with_model(monkeypatch, [])

    with pytest.raises(PoseEstimatorError, match="ya esta abierto"):
        facade.open()


def test_facade_open_failure_wraps_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing(*, model_path: str) -> _FakeModel:
        raise OSError(f"falta {model_path}")

    monkeypatch.setattr(pose_module, "_create_pose_model", failing)

    with pytest.raises(PoseEstimatorError, match="No se pudo cargar"):
        UltralyticsPoseFacade(PostureConfig()).open()


def test_facade_predict_failure_wraps_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BrokenModel(_FakeModel):
        def predict(self, source: object, *, conf: float, verbose: bool) -> list[_FakeResult]:
            _ = (source, conf, verbose)
            raise RuntimeError(" exploto el runtime")

    monkeypatch.setattr(
        pose_module,
        "_create_pose_model",
        lambda *, model_path: _BrokenModel([]),  # noqa: ARG005
    )
    facade = UltralyticsPoseFacade(PostureConfig())
    facade.open()

    with pytest.raises(PoseEstimatorError, match="Fallo la estimacion"):
        facade.estimate(frame_bgr=_frame().data, min_confidence=0.5)


def test_facade_close_is_idempotent() -> None:
    facade = UltralyticsPoseFacade(PostureConfig())

    facade.close()
    facade.close()


# --- Estimador con fachada inyectada ---


class _FakeFacade:
    """Fachada fake que registra las llamadas del estimador."""

    def __init__(self, config: PoseEstimatorConfig) -> None:
        self.config = config
        self.poses: tuple[Pose, ...] = ()
        self.open_calls = 0
        self.close_calls = 0
        self.seen_min_confidence: list[float] = []

    def open(self) -> None:
        self.open_calls += 1

    def estimate(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        min_confidence: float,
    ) -> tuple[Pose, ...]:
        _ = frame_bgr
        self.seen_min_confidence.append(min_confidence)
        return self.poses

    def close(self) -> None:
        self.close_calls += 1


def _estimator_with_fake(
    script: tuple[Pose, ...] = (),
) -> tuple[UltralyticsPoseEstimator, _FakeFacade]:
    fake: _FakeFacade | None = None

    def factory(config: PoseEstimatorConfig) -> _FakeFacade:
        nonlocal fake
        fake = _FakeFacade(config)
        fake.poses = script
        return fake

    estimator = UltralyticsPoseEstimator(PostureConfig(), facade_factory=factory)
    assert fake is None
    estimator.open()
    assert fake is not None
    return estimator, fake


def test_estimator_delegates_to_facade_with_config_confidence() -> None:
    pose = Pose(confidence=0.9)
    estimator, fake = _estimator_with_fake((pose,))

    found = estimator.estimate(_frame())

    assert found == (pose,)
    assert fake.open_calls == 1
    assert fake.seen_min_confidence == [PostureConfig().min_confidence]


def test_estimator_open_twice_raises() -> None:
    estimator, _ = _estimator_with_fake()

    with pytest.raises(PoseEstimatorError, match="ya esta abierto"):
        estimator.open()


def test_estimator_estimate_without_open_raises() -> None:
    estimator = UltralyticsPoseEstimator(PostureConfig(), facade_factory=_FakeFacade)

    with pytest.raises(PoseEstimatorError, match="no esta abierto"):
        estimator.estimate(_frame())


def test_estimator_close_is_idempotent_and_releases_facade() -> None:
    estimator, fake = _estimator_with_fake()

    estimator.close()
    estimator.close()

    assert fake.close_calls == 1
    with pytest.raises(PoseEstimatorError, match="no esta abierto"):
        estimator.estimate(_frame())


def test_estimator_context_manager_opens_and_closes() -> None:
    seen: list[_FakeFacade] = []

    def factory(config: PoseEstimatorConfig) -> _FakeFacade:
        fake = _FakeFacade(config)
        seen.append(fake)
        return fake

    with UltralyticsPoseEstimator(PostureConfig(), facade_factory=factory):
        pass

    assert len(seen) == 1
    assert seen[0].open_calls == 1
    assert seen[0].close_calls == 1


def test_estimator_satisfies_pose_estimator_protocol() -> None:
    estimator: PoseEstimator = UltralyticsPoseEstimator(PostureConfig())

    with pytest.raises(PoseEstimatorError, match="no esta abierto"):
        estimator.estimate(_frame())
