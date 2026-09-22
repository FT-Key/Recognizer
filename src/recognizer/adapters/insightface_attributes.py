"""Edad y genero con InsightFace (deteccion + genderage, sin embeddings).

Reutiliza el bootstrap del reconocedor facial (``buffalo_s``) con los modulos de
deteccion y ``genderage``: una sola via de inferencia ubica cada rostro y estima
sus atributos sobre el recorte alineado. No calcula embeddings ni identidades.
"""

import logging
import math
from collections.abc import Callable
from typing import Protocol, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.adapters.insightface_recognizer import create_analysis
from recognizer.core.constants import MAX_ESTIMATED_AGE, MIN_ESTIMATED_AGE
from recognizer.core.domain.face import FaceBox
from recognizer.core.domain.face_attributes import FaceAttributes, FaceGender
from recognizer.core.domain.frame import Frame
from recognizer.core.errors import FaceAttributeError
from recognizer.core.ports.face_attributes import (
    FaceAttributeEstimator,
    FaceAttributeEstimatorConfig,
)

LOGGER = logging.getLogger("recognizer.gender_age")

FACE_ATTRIBUTE_MODULES = ("detection", "genderage")
# Clases del modelo genderage: 0 = femenino, 1 = masculino (ver
# insightface/model_zoo/attribute.py, ``np.argmax(pred[:2])``).
GENDERAGE_FEMALE_CLASS = 0
GENDERAGE_MALE_CLASS = 1


class _BoxLike(Protocol):
    """Caja facial en pixeles (x_min, y_min, x_max, y_max)."""

    def __len__(self) -> int: ...
    def __getitem__(self, index: int) -> float: ...


class _FaceLike(Protocol):
    """Subconjunto de insightface.app.common.Face que usa el estimador."""

    @property
    def bbox(self) -> _BoxLike: ...
    @property
    def det_score(self) -> float: ...
    @property
    def gender(self) -> int | None: ...
    @property
    def age(self) -> int | None: ...


class _AnalysisLike(Protocol):
    """Subconjunto de insightface.app.FaceAnalysis que usa el estimador."""

    def prepare(self, *, ctx_id: int, det_size: tuple[int, int]) -> None: ...
    def get(self, image_rgb: NDArray[np.uint8]) -> list[_FaceLike]: ...


class FaceAttributeFacade(Protocol):
    """Contrato de la fachada que aisla InsightFace del estimador."""

    def open(self) -> None:
        """Prepara la fachada y carga el modelo."""
        ...

    def estimate(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        min_confidence: float,
    ) -> tuple[FaceAttributes, ...]:
        """Estima edad y genero de los rostros del fotograma BGR."""
        ...

    def close(self) -> None:
        """Libera los recursos de la fachada."""
        ...


def _clamp01(value: float) -> float:
    """Recorta al rango 0..1; NaN cae al minimo."""
    if not math.isfinite(value):
        return 0.0
    return max(0.0, min(1.0, value))


def _map_gender(value: int | None) -> FaceGender:
    """Genero del modelo: 1 = masculino, 0 = femenino, otro/None = desconocido."""
    if value == GENDERAGE_MALE_CLASS:
        return FaceGender.MALE
    if value == GENDERAGE_FEMALE_CLASS:
        return FaceGender.FEMALE
    return FaceGender.UNKNOWN


def _map_attributes(
    *,
    face: _FaceLike,
    width: int,
    height: int,
    min_confidence: float,
) -> FaceAttributes | None:
    """Atributos de un rostro; ``None`` si es debil, degenerado o sin edad."""
    confidence = float(face.det_score)
    if not math.isfinite(confidence) or confidence < min_confidence:
        return None
    raw_age = face.age
    if raw_age is None:
        return None
    box = face.bbox
    x_min_px = int(float(box[0]))
    y_min_px = int(float(box[1]))
    x_max_px = int(float(box[2]))
    y_max_px = int(float(box[3]))
    if x_max_px <= x_min_px or y_max_px <= y_min_px:
        return None
    return FaceAttributes(
        box=FaceBox(
            x_min=_clamp01(x_min_px / width),
            y_min=_clamp01(y_min_px / height),
            x_max=_clamp01(x_max_px / width),
            y_max=_clamp01(y_max_px / height),
            confidence=max(0.0, min(1.0, confidence)),
        ),
        age=max(MIN_ESTIMATED_AGE, min(MAX_ESTIMATED_AGE, int(raw_age))),
        gender=_map_gender(face.gender),
    )


class InsightFaceAttributesFacade:
    """Fachada real sobre InsightFace (import perezoso, solo CPU)."""

    def __init__(self, config: FaceAttributeEstimatorConfig) -> None:
        self._config = config
        self._analysis: _AnalysisLike | None = None

    def open(self) -> None:
        """Carga el modelo buffalo con los modulos de deteccion y genderage.

        Raises:
            FaceAttributeError: si ya estaba abierto o el modelo no carga.
        """
        if self._analysis is not None:
            msg = "El estimador de edad/genero ya esta abierto."
            raise FaceAttributeError(msg)
        try:
            analysis = cast(
                "_AnalysisLike",
                create_analysis(
                    model_path=self._config.model_path,
                    modules=FACE_ATTRIBUTE_MODULES,
                ),
            )
            analysis.prepare(ctx_id=0, det_size=(self._config.det_size, self._config.det_size))
        except (OSError, RuntimeError, ValueError, ImportError) as exc:
            msg = f"No se pudo cargar el estimador de edad/genero: {self._config.model_path}"
            raise FaceAttributeError(msg) from exc
        self._analysis = analysis

    def estimate(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        min_confidence: float,
    ) -> tuple[FaceAttributes, ...]:
        """Estima edad y genero de los rostros del fotograma BGR.

        Raises:
            FaceAttributeError: si se llama antes de open() o InsightFace falla.
        """
        if self._analysis is None:
            msg = "El estimador de edad/genero no esta abierto: llama a open() antes."
            raise FaceAttributeError(msg)
        rgb = cast("NDArray[np.uint8]", cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        height, width = frame_bgr.shape[:2]
        try:
            faces = self._analysis.get(rgb)
        except (RuntimeError, ValueError) as exc:
            msg = "Fallo la estimacion de edad/genero de InsightFace."
            raise FaceAttributeError(msg) from exc
        attributes: list[FaceAttributes] = []
        for face in faces:
            mapped = _map_attributes(
                face=face,
                width=width,
                height=height,
                min_confidence=min_confidence,
            )
            if mapped is not None:
                attributes.append(mapped)
        return tuple(attributes)

    def close(self) -> None:
        """Olvida el modelo; es idempotente."""
        self._analysis = None


class InsightFaceAttributeEstimator(FaceAttributeEstimator):
    """Estimador de edad/genero InsightFace; la fachada es inyectable para tests."""

    def __init__(
        self,
        config: FaceAttributeEstimatorConfig,
        facade_factory: Callable[[FaceAttributeEstimatorConfig], FaceAttributeFacade] | None = None,
    ) -> None:
        self._config = config
        self._facade_factory = facade_factory or InsightFaceAttributesFacade
        self._facade: FaceAttributeFacade | None = None

    def open(self) -> None:
        """Crea y abre la fachada (import perezoso de insightface).

        Raises:
            FaceAttributeError: si ya estaba abierto o la fachada fallo.
        """
        if self._facade is not None:
            msg = "El estimador de edad/genero ya esta abierto."
            raise FaceAttributeError(msg)
        facade = self._facade_factory(self._config)
        facade.open()
        self._facade = facade
        LOGGER.info("Estimador de edad/genero listo (%s).", self._config.model_path)

    def estimate(self, frame: Frame) -> tuple[FaceAttributes, ...]:
        """Estima edad y genero de los rostros del fotograma.

        Raises:
            FaceAttributeError: si se llama sin haber abierto el estimador.
        """
        if self._facade is None:
            msg = "El estimador de edad/genero no esta abierto: llama a open() antes."
            raise FaceAttributeError(msg)
        return self._facade.estimate(
            frame_bgr=frame.data,
            min_confidence=self._config.min_confidence,
        )

    def close(self) -> None:
        """Cierra la fachada; es idempotente."""
        if self._facade is not None:
            self._facade.close()
            self._facade = None

    def __enter__(self) -> "InsightFaceAttributeEstimator":
        self.open()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
