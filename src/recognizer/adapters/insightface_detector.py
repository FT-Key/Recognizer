"""Deteccion facial con InsightFace (solo deteccion, sin embedding).

Reutiliza el bootstrap del reconocedor facial (``buffalo_s``) pero carga solo
el modulo de deteccion: la app de privacidad no necesita identidades y asi el
fotograma se procesa mas rapido.
"""

import logging
import math
from collections.abc import Callable
from typing import Protocol, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.adapters.insightface_recognizer import create_analysis
from recognizer.core.domain.face import FaceBox
from recognizer.core.domain.frame import Frame
from recognizer.core.errors import FaceDetectorError
from recognizer.core.ports.face_detector import FaceDetector, FaceDetectorConfig

LOGGER = logging.getLogger("recognizer.privacy")

DETECTION_MODULES = ("detection",)


class _BoxLike(Protocol):
    """Caja facial en pixeles (x_min, y_min, x_max, y_max)."""

    def __len__(self) -> int: ...
    def __getitem__(self, index: int) -> float: ...


class _FaceLike(Protocol):
    """Subconjunto de insightface.app.common.Face que usa el detector."""

    @property
    def bbox(self) -> _BoxLike: ...
    @property
    def det_score(self) -> float: ...


class _AnalysisLike(Protocol):
    """Subconjunto de insightface.app.FaceAnalysis que usa el detector."""

    def prepare(self, *, ctx_id: int, det_size: tuple[int, int]) -> None: ...
    def get(self, image_rgb: NDArray[np.uint8]) -> list[_FaceLike]: ...


class FaceDetectionFacade(Protocol):
    """Contrato de la fachada que aisla InsightFace del detector."""

    def open(self) -> None:
        """Prepara la fachada y carga el modelo."""
        ...

    def detect(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        min_confidence: float,
    ) -> tuple[FaceBox, ...]:
        """Detecta las cajas de los rostros del fotograma BGR."""
        ...

    def close(self) -> None:
        """Libera los recursos de la fachada."""
        ...


def _clamp01(value: float) -> float:
    """Recorta al rango 0..1; NaN cae al minimo."""
    if not math.isfinite(value):
        return 0.0
    return max(0.0, min(1.0, value))


def _map_box(
    *,
    face: _FaceLike,
    width: int,
    height: int,
    min_confidence: float,
) -> FaceBox | None:
    """Caja normalizada de un rostro; ``None`` si es debil o degenerada."""
    confidence = float(face.det_score)
    if not math.isfinite(confidence) or confidence < min_confidence:
        return None
    box = face.bbox
    x_min_px = int(float(box[0]))
    y_min_px = int(float(box[1]))
    x_max_px = int(float(box[2]))
    y_max_px = int(float(box[3]))
    if x_max_px <= x_min_px or y_max_px <= y_min_px:
        return None
    return FaceBox(
        x_min=_clamp01(x_min_px / width),
        y_min=_clamp01(y_min_px / height),
        x_max=_clamp01(x_max_px / width),
        y_max=_clamp01(y_max_px / height),
        confidence=max(0.0, min(1.0, confidence)),
    )


class InsightFaceDetectionFacade:
    """Fachada real sobre InsightFace (import perezoso, solo CPU)."""

    def __init__(self, config: FaceDetectorConfig, *, det_size: int | None = None) -> None:
        self._config = config
        self._det_size = det_size if det_size is not None else config.det_size
        self._analysis: _AnalysisLike | None = None

    def open(self) -> None:
        """Carga el modelo buffalo con el modulo de deteccion.

        Raises:
            FaceDetectorError: si ya estaba abierto o el modelo no carga.
        """
        if self._analysis is not None:
            msg = "El detector facial ya esta abierto."
            raise FaceDetectorError(msg)
        try:
            analysis = cast(
                "_AnalysisLike",
                create_analysis(model_path=self._config.model_path, modules=DETECTION_MODULES),
            )
            analysis.prepare(ctx_id=0, det_size=(self._det_size, self._det_size))
        except (OSError, RuntimeError, ValueError, ImportError) as exc:
            msg = f"No se pudo cargar el detector facial: {self._config.model_path}"
            raise FaceDetectorError(msg) from exc
        self._analysis = analysis

    def detect(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        min_confidence: float,
    ) -> tuple[FaceBox, ...]:
        """Detecta las cajas de los rostros del fotograma BGR.

        Raises:
            FaceDetectorError: si se llama antes de open() o InsightFace falla.
        """
        if self._analysis is None:
            msg = "El detector facial no esta abierto: llama a open() antes."
            raise FaceDetectorError(msg)
        rgb = cast("NDArray[np.uint8]", cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        height, width = frame_bgr.shape[:2]
        try:
            faces = self._analysis.get(rgb)
        except (RuntimeError, ValueError) as exc:
            msg = "Fallo la deteccion facial de InsightFace."
            raise FaceDetectorError(msg) from exc
        boxes: list[FaceBox] = []
        for face in faces:
            mapped = _map_box(
                face=face,
                width=width,
                height=height,
                min_confidence=min_confidence,
            )
            if mapped is not None:
                boxes.append(mapped)
        return tuple(boxes)

    def close(self) -> None:
        """Olvida el modelo; es idempotente."""
        self._analysis = None


class InsightFaceFaceDetector(FaceDetector):
    """Detector facial InsightFace; la fachada es inyectable para tests."""

    def __init__(
        self,
        config: FaceDetectorConfig,
        facade_factory: Callable[[FaceDetectorConfig], FaceDetectionFacade] | None = None,
    ) -> None:
        self._config = config
        self._facade_factory = facade_factory or InsightFaceDetectionFacade
        self._facade: FaceDetectionFacade | None = None

    def open(self) -> None:
        """Crea y abre la fachada (import perezoso de insightface).

        Raises:
            FaceDetectorError: si ya estaba abierto o la fachada fallo.
        """
        if self._facade is not None:
            msg = "El detector facial ya esta abierto."
            raise FaceDetectorError(msg)
        facade = self._facade_factory(self._config)
        facade.open()
        self._facade = facade
        LOGGER.info("Detector facial listo (%s).", self._config.model_path)

    def detect(self, frame: Frame) -> tuple[FaceBox, ...]:
        """Detecta los rostros del fotograma.

        Raises:
            FaceDetectorError: si se llama sin haber abierto el detector.
        """
        if self._facade is None:
            msg = "El detector facial no esta abierto: llama a open() antes."
            raise FaceDetectorError(msg)
        return self._facade.detect(frame_bgr=frame.data, min_confidence=self._config.min_confidence)

    def close(self) -> None:
        """Cierra la fachada; es idempotente."""
        if self._facade is not None:
            self._facade.close()
            self._facade = None

    def __enter__(self) -> "InsightFaceFaceDetector":
        self.open()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
