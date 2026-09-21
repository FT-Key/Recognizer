"""Reconocimiento facial con InsightFace (buffalo_s, CPU)."""

import logging
import math
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.core.domain.face import FaceBox, FaceObservation
from recognizer.core.domain.frame import Frame
from recognizer.core.errors import FaceRecognizerError
from recognizer.core.ports.face_recognizer import FaceRecognizer, FaceRecognizerConfig

LOGGER = logging.getLogger("recognizer.face")

CPU_PROVIDER = "CPUExecutionProvider"
# Solo deteccion + reconocimiento: landmarks (2d106/3d68) y genero/edad no se
# usan y se ejecutan por cara, encareciendo mucho el frame cuando hay rostro.
FACE_ANALYSIS_MODULES = ("detection", "recognition")
MIN_BOX_SIDE_PX = 1
LAPLACIAN_DEPTH = cv2.CV_64F


class _EmbeddingLike(Protocol):
    """Embedding de un rostro con conversion a lista."""

    def __len__(self) -> int: ...
    def __getitem__(self, index: int) -> float: ...


class _BoxLike(Protocol):
    """Caja facial en pixeles (x_min, y_min, x_max, y_max)."""

    def __len__(self) -> int: ...
    def __getitem__(self, index: int) -> float: ...


class _FaceLike(Protocol):
    """Subconjunto de insightface.app.common.Face que usamos."""

    @property
    def embedding(self) -> _EmbeddingLike | None: ...
    @property
    def bbox(self) -> _BoxLike: ...
    @property
    def det_score(self) -> float: ...


class _AnalysisLike(Protocol):
    """Subconjunto de insightface.app.FaceAnalysis que usamos."""

    def prepare(self, *, ctx_id: int, det_size: tuple[int, int]) -> None: ...
    def get(self, image_rgb: NDArray[np.uint8]) -> list[_FaceLike]: ...


class FaceAnalysisFacade(Protocol):
    """Contrato de la fachada que aisla InsightFace del reconocedor."""

    def open(self) -> None:
        """Prepara la fachada y carga el modelo."""
        ...

    def recognize(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        min_confidence: float,
    ) -> tuple[FaceObservation, ...]:
        """Detecta rostros en el fotograma BGR con embedding normalizado."""
        ...

    def close(self) -> None:
        """Libera los recursos de la fachada."""
        ...


def split_model_path(model_path: str) -> tuple[str, str]:
    """Divide ``models/buffalo_s`` en raiz (``models``) y nombre (``buffalo_s``)."""
    candidate = Path(model_path)
    name = candidate.name
    parent = str(candidate.parent) if str(candidate.parent) not in ("", ".") else "models"
    return parent, name


def create_analysis(
    *, model_path: str, modules: tuple[str, ...] = FACE_ANALYSIS_MODULES
) -> _AnalysisLike:
    """Crea la fachada de InsightFace con los modulos pedidos (import perezoso)."""
    from insightface.app import FaceAnalysis

    root, name = split_model_path(model_path)
    analysis = FaceAnalysis(
        name=name,
        root=root,
        providers=[CPU_PROVIDER],
        allowed_modules=list(modules),
    )
    return cast("_AnalysisLike", analysis)


def _clamp01(value: float) -> float:
    """Recorta al rango 0..1; NaN cae al minimo."""
    if not math.isfinite(value):
        return 0.0
    return max(0.0, min(1.0, value))


def _normalize_embedding(values: _EmbeddingLike) -> tuple[float, ...]:
    """Embedding a norma unitaria; el vector nulo queda en ceros."""
    raw = tuple(float(values[index]) for index in range(len(values)))
    norm = math.sqrt(sum(value * value for value in raw))
    if norm <= 1e-9:
        return tuple(0.0 for _ in raw)
    return tuple(value / norm for value in raw)


def _sharpness(*, gray: NDArray[np.uint8], x_min: int, y_min: int, x_max: int, y_max: int) -> float:
    """Nitidez del recorte facial via varianza del Laplaciano."""
    height, width = gray.shape[:2]
    left = max(0, min(x_min, width - MIN_BOX_SIDE_PX))
    top = max(0, min(y_min, height - MIN_BOX_SIDE_PX))
    right = max(left + MIN_BOX_SIDE_PX, min(x_max, width))
    bottom = max(top + MIN_BOX_SIDE_PX, min(y_max, height))
    crop = gray[top:bottom, left:right]
    laplacian = cv2.Laplacian(crop, LAPLACIAN_DEPTH)
    return float(laplacian.var())


def _map_face(
    *,
    face: _FaceLike,
    width: int,
    height: int,
    gray: NDArray[np.uint8],
    min_confidence: float,
) -> FaceObservation | None:
    confidence = float(face.det_score)
    if not math.isfinite(confidence):
        return None
    if confidence < min_confidence:
        return None
    embedding = face.embedding
    if embedding is None or len(embedding) == 0:
        return None
    box = face.bbox
    x_min_px = int(float(box[0]))
    y_min_px = int(float(box[1]))
    x_max_px = int(float(box[2]))
    y_max_px = int(float(box[3]))
    if x_max_px <= x_min_px or y_max_px <= y_min_px:
        return None
    face_box = FaceBox(
        x_min=_clamp01(x_min_px / width),
        y_min=_clamp01(y_min_px / height),
        x_max=_clamp01(x_max_px / width),
        y_max=_clamp01(y_max_px / height),
        confidence=max(0.0, min(1.0, confidence)),
    )
    sharpness = _sharpness(
        gray=gray, x_min=x_min_px, y_min=y_min_px, x_max=x_max_px, y_max=y_max_px
    )
    return FaceObservation(
        embedding=_normalize_embedding(embedding), box=face_box, sharpness=sharpness
    )


class InsightFaceFacade:
    """Fachada real sobre InsightFace (import perezoso, solo CPU)."""

    def __init__(self, config: FaceRecognizerConfig, *, det_size: int | None = None) -> None:
        self._config = config
        self._det_size = det_size if det_size is not None else config.det_size
        self._analysis: _AnalysisLike | None = None

    def open(self) -> None:
        """Carga el modelo buffalo (lo descarga si falta).

        Raises:
            FaceRecognizerError: si ya estaba abierto o el modelo no carga.
        """
        if self._analysis is not None:
            msg = "El reconocedor facial ya esta abierto."
            raise FaceRecognizerError(msg)
        try:
            analysis = create_analysis(model_path=self._config.model_path)
            analysis.prepare(ctx_id=0, det_size=(self._det_size, self._det_size))
        except (OSError, RuntimeError, ValueError, ImportError) as exc:
            msg = f"No se pudo cargar el modelo facial: {self._config.model_path}"
            raise FaceRecognizerError(msg) from exc
        self._analysis = analysis

    def recognize(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        min_confidence: float,
    ) -> tuple[FaceObservation, ...]:
        """Detecta rostros del fotograma BGR.

        Raises:
            FaceRecognizerError: si se llama antes de open() o InsightFace falla.
        """
        if self._analysis is None:
            msg = "El reconocedor facial no esta abierto: llama a open() antes."
            raise FaceRecognizerError(msg)
        rgb = cast("NDArray[np.uint8]", cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        gray = cast("NDArray[np.uint8]", cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY))
        height, width = frame_bgr.shape[:2]
        try:
            faces = self._analysis.get(rgb)
        except (RuntimeError, ValueError) as exc:
            msg = "Fallo el reconocimiento facial de InsightFace."
            raise FaceRecognizerError(msg) from exc
        observations: list[FaceObservation] = []
        for face in faces:
            observation = _map_face(
                face=face,
                width=width,
                height=height,
                gray=gray,
                min_confidence=min_confidence,
            )
            if observation is not None:
                observations.append(observation)
        return tuple(observations)

    def close(self) -> None:
        """Olvida el modelo; es idempotente."""
        self._analysis = None


class InsightFaceRecognizer(FaceRecognizer):
    """Reconocedor facial InsightFace; la fachada es inyectable para tests."""

    def __init__(
        self,
        config: FaceRecognizerConfig,
        facade_factory: Callable[[FaceRecognizerConfig], FaceAnalysisFacade] | None = None,
    ) -> None:
        self._config = config
        self._facade_factory = facade_factory or InsightFaceFacade
        self._facade: FaceAnalysisFacade | None = None

    def open(self) -> None:
        """Crea y abre la fachada (import perezoso de insightface).

        Raises:
            FaceRecognizerError: si ya estaba abierto o la fachada fallo.
        """
        if self._facade is not None:
            msg = "El reconocedor facial ya esta abierto."
            raise FaceRecognizerError(msg)
        facade = self._facade_factory(self._config)
        facade.open()
        self._facade = facade
        LOGGER.info("Modelo facial listo (%s).", self._config.model_path)

    def recognize(self, frame: Frame) -> tuple[FaceObservation, ...]:
        """Reconoce los rostros del fotograma.

        Raises:
            FaceRecognizerError: si se llama sin haber abierto el reconocedor.
        """
        if self._facade is None:
            msg = "El reconocedor facial no esta abierto: llama a open() antes."
            raise FaceRecognizerError(msg)
        return self._facade.recognize(
            frame_bgr=frame.data, min_confidence=self._config.min_confidence
        )

    def close(self) -> None:
        """Cierra la fachada; es idempotente."""
        if self._facade is not None:
            self._facade.close()
            self._facade = None

    def __enter__(self) -> "InsightFaceRecognizer":
        self.open()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
