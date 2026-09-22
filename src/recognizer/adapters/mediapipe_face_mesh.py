"""Adaptador de deteccion de landmarks faciales basado en MediaPipe Tasks."""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.core.constants import MILLISECONDS_PER_SECOND
from recognizer.core.domain.face_landmarks import (
    FaceLandmark3D,
    FaceMeshResult,
    compute_face_mesh_metrics,
)
from recognizer.core.domain.frame import Frame
from recognizer.core.errors import FaceMeshError
from recognizer.core.ports.face_mesh_landmarker import FaceMeshConfig


class _LandmarkLike(Protocol):
    """Subconjunto de NormalizedLandmark que usamos."""

    x: float
    y: float
    z: float


class _ResultLike(Protocol):
    """Subconjunto de FaceLandmarkerResult que usamos."""

    face_landmarks: Sequence[Sequence[_LandmarkLike]]


class _LandmarkerLike(Protocol):
    """Subconjunto de FaceLandmarker que usamos (permite dobles en tests)."""

    def detect_for_video(self, image: object, timestamp_ms: int) -> _ResultLike:
        """Detecta landmarks faciales en una imagen con marca de tiempo."""
        ...

    def close(self) -> None:
        """Libera el landmarker."""
        ...


class FaceMeshFacade(Protocol):
    """Contrato de la fachada que aisla MediaPipe del landmarker."""

    def open(self) -> None:
        """Prepara la fachada y carga el modelo."""
        ...

    def detect(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        timestamp_ms: int,
    ) -> tuple[FaceMeshResult, ...]:
        """Detecta landmarks faciales en el fotograma BGR."""
        ...

    def close(self) -> None:
        """Libera los recursos de la fachada."""
        ...


def _create_landmarker(*, config: FaceMeshConfig, model_path: Path) -> _LandmarkerLike:
    from mediapipe.tasks.python import BaseOptions, vision

    options = vision.FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.VIDEO,
        min_face_detection_confidence=config.min_face_detection_confidence,
        min_face_presence_confidence=config.min_face_presence_confidence,
        num_faces=1,
    )
    # mediapipe no expone stubs: el cast fija la frontera tipada con la libreria.
    return cast("_LandmarkerLike", vision.FaceLandmarker.create_from_options(options))


def _to_mp_image(frame_bgr: NDArray[np.uint8]) -> object:
    import mediapipe as mp

    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    # mp.Image tampoco tiene stubs: el cast fija la frontera tipada con la libreria.
    return cast("object", mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))


def _map_face(landmarks: Sequence[_LandmarkLike]) -> FaceMeshResult:
    """Convierte los 468 landmarks de MediaPipe a nuestro dominio y calcula EAR/MAR."""
    points = tuple(FaceLandmark3D(x=float(lm.x), y=float(lm.y), z=float(lm.z)) for lm in landmarks)
    return compute_face_mesh_metrics(points)


def _map_result(result: _ResultLike) -> tuple[FaceMeshResult, ...]:
    faces: list[FaceMeshResult] = []
    for face_landmarks in result.face_landmarks:
        faces.append(_map_face(face_landmarks))
    return tuple(faces)


class MediaPipeFaceMeshFacade:
    """Fachada real sobre mediapipe.tasks.python.vision.FaceLandmarker."""

    def __init__(self, config: FaceMeshConfig) -> None:
        self._config = config
        self._landmarker: _LandmarkerLike | None = None

    def open(self) -> None:
        """Crea el FaceLandmarker en modo VIDEO.

        Raises:
            FaceMeshError: si ya estaba abierto o el modelo no puede cargarse.
        """
        if self._landmarker is not None:
            msg = "El FaceLandmarker de MediaPipe ya esta abierto."
            raise FaceMeshError(msg)

        model_path = Path(self._config.model_path)
        if not model_path.is_file():
            msg = f"No existe el modelo de face mesh: {model_path}"
            raise FaceMeshError(msg)

        try:
            self._landmarker = _create_landmarker(config=self._config, model_path=model_path)
        except (OSError, RuntimeError, ValueError) as exc:
            msg = f"No se pudo cargar el modelo de face mesh: {model_path}"
            raise FaceMeshError(msg) from exc

    def detect(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        timestamp_ms: int,
    ) -> tuple[FaceMeshResult, ...]:
        """Detecta landmarks faciales en el fotograma BGR.

        Raises:
            FaceMeshError: si se llama antes de open() o si el runtime de
                MediaPipe/cv2 falla durante la deteccion.
        """
        if self._landmarker is None:
            msg = "El FaceLandmarker no esta abierto: llama a open() antes de detect()."
            raise FaceMeshError(msg)

        try:
            image = _to_mp_image(frame_bgr)
            result = self._landmarker.detect_for_video(image, timestamp_ms)
        except (cv2.error, RuntimeError, ValueError) as exc:
            msg = "Fallo la deteccion de face mesh en MediaPipe."
            raise FaceMeshError(msg) from exc
        return _map_result(result)

    def close(self) -> None:
        """Cierra el FaceLandmarker si esta abierto."""
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None


class MediaPipeFaceMesh:
    """Detecta landmarks faciales con MediaPipe Tasks; la fachada es inyectable para tests."""

    def __init__(
        self,
        config: FaceMeshConfig,
        facade_factory: Callable[[FaceMeshConfig], FaceMeshFacade] | None = None,
    ) -> None:
        self._config = config
        self._facade_factory = facade_factory or MediaPipeFaceMeshFacade
        self._facade: FaceMeshFacade | None = None

    def open(self) -> None:
        """Crea y abre la fachada del landmarker.

        Raises:
            FaceMeshError: si el landmarker ya estaba abierto o la fachada fallo.
        """
        if self._facade is not None:
            msg = "El FaceLandmarker ya esta abierto."
            raise FaceMeshError(msg)

        facade = self._facade_factory(self._config)
        facade.open()
        self._facade = facade

    def detect(self, frame: Frame) -> tuple[FaceMeshResult, ...]:
        """Detecta los landmarks faciales del fotograma.

        Raises:
            FaceMeshError: si se llama sin haber abierto el landmarker.
        """
        if self._facade is None:
            msg = "El FaceLandmarker no esta abierto: llama a open() antes de detect()."
            raise FaceMeshError(msg)

        timestamp_ms = int(frame.timestamp * MILLISECONDS_PER_SECOND)
        return self._facade.detect(frame_bgr=frame.data, timestamp_ms=timestamp_ms)

    def close(self) -> None:
        """Cierra la fachada; es idempotente."""
        if self._facade is not None:
            self._facade.close()
            self._facade = None

    def __enter__(self) -> "MediaPipeFaceMesh":
        self.open()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
