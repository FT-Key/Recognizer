"""Adaptador de estimacion de postura basado en Ultralytics YOLO pose."""

import math
from collections.abc import Callable
from typing import Protocol, cast

import numpy as np
from numpy.typing import NDArray

from recognizer.core.domain.detection import (
    MAX_CONFIDENCE,
    MAX_NORMALIZED_COORDINATE,
    MIN_CONFIDENCE,
    MIN_NORMALIZED_COORDINATE,
)
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.pose import COCO_KEYPOINT_ORDER, Keypoint, Pose
from recognizer.core.errors import PoseEstimatorError
from recognizer.core.ports.pose_estimator import PoseEstimator, PoseEstimatorConfig


class _ScalarLike(Protocol):
    """Escalar de tensor con conversion a numero."""

    def __float__(self) -> float: ...


class _PointLike(Protocol):
    """Un punto (x, y) de un tensor de keypoints."""

    def __len__(self) -> int: ...
    def __getitem__(self, index: int) -> _ScalarLike: ...


class _KeypointMatrixLike(Protocol):
    """Keypoints de una persona (K, 2)."""

    def __len__(self) -> int: ...
    def __getitem__(self, index: int) -> _PointLike: ...


class _KeypointBatchLike(Protocol):
    """Keypoints normalizados de todas las personas (N, K, 2)."""

    def __len__(self) -> int: ...
    def __getitem__(self, index: int) -> _KeypointMatrixLike: ...


class _VectorLike(Protocol):
    """Vector de confianzas de una persona (K,)."""

    def __len__(self) -> int: ...
    def __getitem__(self, index: int) -> _ScalarLike: ...


class _ConfMatrixLike(Protocol):
    """Confianzas de keypoints (N, K)."""

    def __len__(self) -> int: ...
    def __getitem__(self, index: int) -> _VectorLike: ...


class _KeypointsLike(Protocol):
    """Subconjunto de ultralytics.engine.results.Keypoints que usamos."""

    @property
    def xyn(self) -> _KeypointBatchLike: ...
    @property
    def conf(self) -> _ConfMatrixLike | None: ...
    def __len__(self) -> int: ...


class _PoseResultLike(Protocol):
    """Subconjunto de ultralytics.engine.results.Results para pose."""

    @property
    def keypoints(self) -> _KeypointsLike | None: ...


class _PoseModelLike(Protocol):
    """Subconjunto de ultralytics.YOLO que usamos (permite dobles en tests)."""

    def predict(self, source: object, *, conf: float, verbose: bool) -> list[_PoseResultLike]: ...


class PoseEstimatorFacade(Protocol):
    """Contrato de la fachada que aisla Ultralytics del estimador de pose."""

    def open(self) -> None:
        """Prepara la fachada y carga el modelo."""
        ...

    def estimate(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        min_confidence: float,
    ) -> tuple[Pose, ...]:
        """Estima las posturas presentes en el fotograma BGR."""
        ...

    def close(self) -> None:
        """Libera los recursos de la fachada."""
        ...


def _create_pose_model(*, model_path: str) -> _PoseModelLike:
    from ultralytics.models.yolo.model import YOLO

    # Ultralytics descarga el .pt si falta; el cast fija la frontera tipada
    # con la libreria.
    return cast("_PoseModelLike", YOLO(model_path))


def _clamp01(value: float) -> float:
    """Recorta un valor al rango normalizado 0..1; NaN cae al minimo."""
    if not math.isfinite(value):
        return MIN_NORMALIZED_COORDINATE
    return max(MIN_NORMALIZED_COORDINATE, min(MAX_NORMALIZED_COORDINATE, value))


def _clamp_confidence(value: float) -> float:
    """Recorta una confianza al rango 0..1; NaN cae al minimo."""
    if not math.isfinite(value):
        return MIN_CONFIDENCE
    return max(MIN_CONFIDENCE, min(MAX_CONFIDENCE, value))


def _pose_confidence(*, keypoints: _KeypointsLike, index: int) -> float:
    """Confianza global de una persona: media de las confianzas de sus puntos."""
    confidences = keypoints.conf
    if confidences is None:
        return MAX_CONFIDENCE
    vector = confidences[index]
    if len(vector) == 0:
        return MAX_CONFIDENCE
    total = sum(float(vector[position]) for position in range(len(vector)))
    return _clamp_confidence(total / len(vector))


def _map_keypoints(*, keypoints: _KeypointsLike, index: int) -> tuple[Keypoint, ...]:
    """Mapea los puntos de una persona al vocabulario del dominio."""
    points = keypoints.xyn[index]
    confidences = keypoints.conf
    mapped: list[Keypoint] = []
    count = min(len(points), len(COCO_KEYPOINT_ORDER))
    for position in range(count):
        point = points[position]
        confidence = (
            float(confidences[index][position]) if confidences is not None else MAX_CONFIDENCE
        )
        mapped.append(
            Keypoint(
                name=COCO_KEYPOINT_ORDER[position],
                x=_clamp01(float(point[0])),
                y=_clamp01(float(point[1])),
                confidence=_clamp_confidence(confidence),
            )
        )
    return tuple(mapped)


def _map_result(*, result: _PoseResultLike, min_confidence: float) -> tuple[Pose, ...]:
    keypoints = result.keypoints
    if keypoints is None:
        return ()
    poses: list[Pose] = []
    for index in range(len(keypoints)):
        confidence = _pose_confidence(keypoints=keypoints, index=index)
        if confidence < min_confidence:
            continue
        mapped = _map_keypoints(keypoints=keypoints, index=index)
        if mapped:
            poses.append(Pose(confidence=confidence, keypoints=mapped))
    return tuple(poses)


def _map_results(*, results: list[_PoseResultLike], min_confidence: float) -> tuple[Pose, ...]:
    poses: list[Pose] = []
    for result in results:
        poses.extend(_map_result(result=result, min_confidence=min_confidence))
    return tuple(poses)


class UltralyticsPoseFacade:
    """Fachada real sobre ultralytics.YOLO (modelo pose)."""

    def __init__(self, config: PoseEstimatorConfig) -> None:
        self._config = config
        self._model: _PoseModelLike | None = None

    def open(self) -> None:
        """Carga el modelo YOLO pose (lo descarga si falta).

        Raises:
            PoseEstimatorError: si ya estaba abierto o el modelo no carga.
        """
        if self._model is not None:
            msg = "El estimador de pose ya esta abierto."
            raise PoseEstimatorError(msg)

        try:
            self._model = _create_pose_model(model_path=self._config.model_path)
        except (OSError, RuntimeError, ValueError) as exc:
            msg = f"No se pudo cargar el modelo YOLO pose: {self._config.model_path}"
            raise PoseEstimatorError(msg) from exc

    def estimate(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        min_confidence: float,
    ) -> tuple[Pose, ...]:
        """Estima las posturas del fotograma BGR.

        Raises:
            PoseEstimatorError: si se llama antes de open() o si Ultralytics falla.
        """
        if self._model is None:
            msg = "El estimador de pose no esta abierto: llama a open() antes de estimate()."
            raise PoseEstimatorError(msg)

        try:
            results = self._model.predict(frame_bgr, conf=min_confidence, verbose=False)
        except (OSError, RuntimeError, ValueError) as exc:
            msg = "Fallo la estimacion de pose en YOLO."
            raise PoseEstimatorError(msg) from exc
        return _map_results(results=results, min_confidence=min_confidence)

    def close(self) -> None:
        """Olvida el modelo; es idempotente."""
        self._model = None


class UltralyticsPoseEstimator(PoseEstimator):
    """Estima posturas con Ultralytics YOLO pose; la fachada es inyectable."""

    def __init__(
        self,
        config: PoseEstimatorConfig,
        facade_factory: Callable[[PoseEstimatorConfig], PoseEstimatorFacade] | None = None,
    ) -> None:
        self._config = config
        self._facade_factory = facade_factory or UltralyticsPoseFacade
        self._facade: PoseEstimatorFacade | None = None

    def open(self) -> None:
        """Crea y abre la fachada del estimador.

        Raises:
            PoseEstimatorError: si ya estaba abierto o la fachada fallo.
        """
        if self._facade is not None:
            msg = "El estimador de pose ya esta abierto."
            raise PoseEstimatorError(msg)

        facade = self._facade_factory(self._config)
        facade.open()
        self._facade = facade

    def estimate(self, frame: Frame) -> tuple[Pose, ...]:
        """Estima las posturas del fotograma.

        Raises:
            PoseEstimatorError: si se llama sin haber abierto el estimador.
        """
        if self._facade is None:
            msg = "El estimador de pose no esta abierto: llama a open() antes de estimate()."
            raise PoseEstimatorError(msg)

        return self._facade.estimate(
            frame_bgr=frame.data, min_confidence=self._config.min_confidence
        )

    def close(self) -> None:
        """Cierra la fachada; es idempotente."""
        if self._facade is not None:
            self._facade.close()
            self._facade = None

    def __enter__(self) -> "UltralyticsPoseEstimator":
        self.open()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
