"""Adaptador de deteccion de objetos basado en Ultralytics YOLO."""

from collections.abc import Callable
from typing import Protocol, cast

import numpy as np
from numpy.typing import NDArray

from recognizer.core.constants import DEFAULT_TRACKER_CONFIG
from recognizer.core.domain.detection import (
    MAX_NORMALIZED_COORDINATE,
    MIN_NORMALIZED_COORDINATE,
    BoundingBox,
    Detection,
)
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.tracking import TrackedDetection
from recognizer.core.errors import DetectorError
from recognizer.core.ports.object_detector import DetectorConfig, ObjectDetector


class _ScalarLike(Protocol):
    """Escalar de tensor con conversion a numero."""

    def __float__(self) -> float: ...
    def __int__(self) -> int: ...


class _VectorLike(Protocol):
    """Vector de tensores de una fila (confianza o clase)."""

    def __len__(self) -> int: ...
    def __getitem__(self, index: int) -> _ScalarLike: ...


class _MatrixLike(Protocol):
    """Matriz de tensores de cajas normalizadas (N, 4)."""

    def __len__(self) -> int: ...
    def __getitem__(self, index: int) -> _VectorLike: ...


class _BoxRowLike(Protocol):
    """Una fila de Boxes de Ultralytics (indexar Boxes devuelve otra Boxes de 1 fila)."""

    @property
    def xyxyn(self) -> _MatrixLike: ...
    @property
    def conf(self) -> _VectorLike: ...
    @property
    def cls(self) -> _VectorLike: ...
    @property
    def id(self) -> _VectorLike | None: ...


class _BoxesLike(Protocol):
    """Subconjunto de ultralytics.engine.results.Boxes que usamos."""

    def __len__(self) -> int: ...
    def __getitem__(self, index: int) -> _BoxRowLike: ...


class _ResultLike(Protocol):
    """Subconjunto de ultralytics.engine.results.Results que usamos."""

    @property
    def boxes(self) -> _BoxesLike | None: ...
    @property
    def names(self) -> dict[int, str]: ...


class _ModelLike(Protocol):
    """Subconjunto de ultralytics.YOLO que usamos (permite dobles en tests)."""

    def predict(self, source: object, *, conf: float, verbose: bool) -> list[_ResultLike]: ...

    def track(
        self,
        source: object,
        *,
        conf: float,
        persist: bool,
        verbose: bool,
        tracker: str,
    ) -> list[_ResultLike]: ...


class ObjectDetectorFacade(Protocol):
    """Contrato de la fachada que aisla Ultralytics del detector."""

    def open(self) -> None:
        """Prepara la fachada y carga el modelo."""
        ...

    def detect(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        min_confidence: float,
    ) -> tuple[Detection, ...]:
        """Detecta objetos en el fotograma BGR."""
        ...

    def track(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        min_confidence: float,
    ) -> tuple[TrackedDetection, ...]:
        """Rastrea objetos en el fotograma BGR devolviendo sus IDs de track."""
        ...

    def close(self) -> None:
        """Libera los recursos de la fachada."""
        ...


def _create_model(*, model_path: str) -> _ModelLike:
    from ultralytics.models.yolo.model import YOLO

    # Ultralytics descarga el .pt si falta; el cast fija la frontera tipada
    # con la libreria.
    return cast("_ModelLike", YOLO(model_path))


def _clamp01(value: float) -> float:
    """Recorta un valor al rango normalizado 0..1."""
    return max(MIN_NORMALIZED_COORDINATE, min(MAX_NORMALIZED_COORDINATE, value))


def _map_row(
    *,
    row: _BoxRowLike,
    names: dict[int, str],
    min_confidence: float,
) -> Detection | None:
    confidence = float(row.conf[0])
    if confidence < min_confidence:
        return None
    label = names.get(int(row.cls[0]))
    if label is None:
        return None
    coords = row.xyxyn[0]
    bbox = BoundingBox(
        x_min=_clamp01(float(coords[0])),
        y_min=_clamp01(float(coords[1])),
        x_max=_clamp01(float(coords[2])),
        y_max=_clamp01(float(coords[3])),
    )
    return Detection(label=label, confidence=confidence, bbox=bbox)


def _map_results(*, results: list[_ResultLike], min_confidence: float) -> tuple[Detection, ...]:
    detections: list[Detection] = []
    for result in results:
        boxes = result.boxes
        if boxes is None:
            continue
        for index in range(len(boxes)):
            detection = _map_row(
                row=boxes[index], names=result.names, min_confidence=min_confidence
            )
            if detection is not None:
                detections.append(detection)
    return tuple(detections)


def _map_tracked_row(
    *,
    row: _BoxRowLike,
    names: dict[int, str],
    min_confidence: float,
) -> TrackedDetection | None:
    """Mapea una fila con ID de track; sin ID (aun sin confirmar) devuelve None."""
    if row.id is None:
        return None
    detection = _map_row(row=row, names=names, min_confidence=min_confidence)
    if detection is None:
        return None
    return TrackedDetection(track_id=int(row.id[0]), detection=detection)


def _map_tracked_results(
    *,
    results: list[_ResultLike],
    min_confidence: float,
) -> tuple[TrackedDetection, ...]:
    tracked: list[TrackedDetection] = []
    for result in results:
        boxes = result.boxes
        if boxes is None:
            continue
        for index in range(len(boxes)):
            item = _map_tracked_row(
                row=boxes[index], names=result.names, min_confidence=min_confidence
            )
            if item is not None:
                tracked.append(item)
    return tuple(tracked)


class UltralyticsDetectorFacade:
    """Fachada real sobre ultralytics.YOLO."""

    def __init__(self, config: DetectorConfig) -> None:
        self._config = config
        self._model: _ModelLike | None = None

    def open(self) -> None:
        """Carga el modelo YOLO (lo descarga si falta).

        Raises:
            DetectorError: si ya estaba abierto o el modelo no puede cargarse.
        """
        if self._model is not None:
            msg = "El detector YOLO ya esta abierto."
            raise DetectorError(msg)

        try:
            self._model = _create_model(model_path=self._config.model_path)
        except (OSError, RuntimeError, ValueError) as exc:
            msg = f"No se pudo cargar el modelo YOLO: {self._config.model_path}"
            raise DetectorError(msg) from exc

    def detect(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        min_confidence: float,
    ) -> tuple[Detection, ...]:
        """Detecta objetos en el fotograma BGR.

        Raises:
            DetectorError: si se llama antes de open() o si el runtime de
                Ultralytics falla durante la deteccion.
        """
        if self._model is None:
            msg = "El detector YOLO no esta abierto: llama a open() antes de detect()."
            raise DetectorError(msg)

        try:
            results = self._model.predict(frame_bgr, conf=min_confidence, verbose=False)
        except (OSError, RuntimeError, ValueError) as exc:
            msg = "Fallo la deteccion de objetos en YOLO."
            raise DetectorError(msg) from exc
        return _map_results(results=results, min_confidence=min_confidence)

    def track(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        min_confidence: float,
    ) -> tuple[TrackedDetection, ...]:
        """Rastrea objetos en el fotograma BGR (una sola via: track incluye deteccion).

        Raises:
            DetectorError: si se llama antes de open() o si el runtime de
                Ultralytics falla durante el tracking.
        """
        if self._model is None:
            msg = "El detector YOLO no esta abierto: llama a open() antes de track()."
            raise DetectorError(msg)

        try:
            results = self._model.track(
                frame_bgr,
                conf=min_confidence,
                persist=True,
                verbose=False,
                tracker=DEFAULT_TRACKER_CONFIG,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            msg = "Fallo el tracking de objetos en YOLO."
            raise DetectorError(msg) from exc
        return _map_tracked_results(results=results, min_confidence=min_confidence)

    def close(self) -> None:
        """Olvida el modelo; es idempotente."""
        self._model = None


class UltralyticsDetector(ObjectDetector):
    """Detecta objetos con Ultralytics YOLO; la fachada es inyectable para tests."""

    def __init__(
        self,
        config: DetectorConfig,
        facade_factory: Callable[[DetectorConfig], ObjectDetectorFacade] | None = None,
    ) -> None:
        self._config = config
        self._facade_factory = facade_factory or UltralyticsDetectorFacade
        self._facade: ObjectDetectorFacade | None = None

    def open(self) -> None:
        """Crea y abre la fachada del detector.

        Raises:
            DetectorError: si el detector ya estaba abierto o la fachada fallo.
        """
        if self._facade is not None:
            msg = "El detector de objetos ya esta abierto."
            raise DetectorError(msg)

        facade = self._facade_factory(self._config)
        facade.open()
        self._facade = facade

    def detect(self, frame: Frame) -> tuple[Detection, ...]:
        """Detecta los objetos del fotograma.

        Raises:
            DetectorError: si se llama sin haber abierto el detector.
        """
        if self._facade is None:
            msg = "El detector de objetos no esta abierto: llama a open() antes de detect()."
            raise DetectorError(msg)

        return self._facade.detect(frame_bgr=frame.data, min_confidence=self._config.min_confidence)

    def track(self, frame: Frame) -> tuple[TrackedDetection, ...]:
        """Rastrea los objetos del fotograma con IDs persistentes.

        Raises:
            DetectorError: si se llama sin haber abierto el detector.
        """
        if self._facade is None:
            msg = "El detector de objetos no esta abierto: llama a open() antes de track()."
            raise DetectorError(msg)

        return self._facade.track(frame_bgr=frame.data, min_confidence=self._config.min_confidence)

    def close(self) -> None:
        """Cierra la fachada; es idempotente."""
        if self._facade is not None:
            self._facade.close()
            self._facade = None

    def __enter__(self) -> "UltralyticsDetector":
        self.open()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
