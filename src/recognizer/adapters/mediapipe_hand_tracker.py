"""Adaptador de deteccion de manos basado en MediaPipe Tasks."""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.core.config import HandsConfig
from recognizer.core.constants import MILLISECONDS_PER_SECOND
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.hand import Handedness, HandLandmarks, Point
from recognizer.core.errors import HandTrackerError
from recognizer.core.ports.hand_tracker import HandTracker

HANDEDNESS_BY_LABEL: dict[str, Handedness] = {
    Handedness.LEFT.value: Handedness.LEFT,
    Handedness.RIGHT.value: Handedness.RIGHT,
    Handedness.UNKNOWN.value: Handedness.UNKNOWN,
}

MISSING_CATEGORY_CONFIDENCE = 0.0


class _LandmarkLike(Protocol):
    """Subconjunto de NormalizedLandmark que usamos."""

    x: float
    y: float
    z: float


class _CategoryLike(Protocol):
    """Subconjunto de Category que usamos."""

    category_name: str
    score: float


class _ResultLike(Protocol):
    """Subconjunto de HandLandmarkerResult que usamos."""

    handedness: Sequence[Sequence[_CategoryLike]]
    hand_landmarks: Sequence[Sequence[_LandmarkLike]]


class _LandmarkerLike(Protocol):
    """Subconjunto de HandLandmarker que usamos (permite dobles en tests)."""

    def detect_for_video(self, image: object, timestamp_ms: int) -> _ResultLike:
        """Detecta manos en una imagen con marca de tiempo."""
        ...

    def close(self) -> None:
        """Libera el landmarker."""
        ...


class HandDetectorFacade(Protocol):
    """Contrato de la fachada que aisla MediaPipe del tracker."""

    def open(self) -> None:
        """Prepara la fachada y carga el modelo."""
        ...

    def detect(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        timestamp_ms: int,
    ) -> tuple[HandLandmarks, ...]:
        """Detecta manos en el fotograma BGR."""
        ...

    def close(self) -> None:
        """Libera los recursos de la fachada."""
        ...


def _create_landmarker(*, config: HandsConfig, model_path: Path) -> _LandmarkerLike:
    from mediapipe.tasks.python import BaseOptions, vision

    options = vision.HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=config.max_hands,
        min_hand_detection_confidence=config.min_detection_confidence,
        min_hand_presence_confidence=config.min_presence_confidence,
        min_tracking_confidence=config.min_tracking_confidence,
    )
    # mediapipe no expone stubs: el cast fija la frontera tipada con la libreria.
    return cast("_LandmarkerLike", vision.HandLandmarker.create_from_options(options))


def _to_mp_image(frame_bgr: NDArray[np.uint8]) -> object:
    import mediapipe as mp

    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    # mp.Image tampoco tiene stubs: el cast fija la frontera tipada con la libreria.
    return cast("object", mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))


def _map_hand(
    *,
    landmarks: Sequence[_LandmarkLike],
    categories: Sequence[_CategoryLike],
) -> HandLandmarks:
    if categories:
        category = categories[0]
        handedness = HANDEDNESS_BY_LABEL.get(category.category_name, Handedness.UNKNOWN)
        confidence = float(category.score)
    else:
        handedness = Handedness.UNKNOWN
        confidence = MISSING_CATEGORY_CONFIDENCE

    points = tuple(
        Point(x=float(landmark.x), y=float(landmark.y), z=float(landmark.z))
        for landmark in landmarks
    )
    return HandLandmarks(handedness=handedness, confidence=confidence, points=points)


def _map_result(result: _ResultLike) -> tuple[HandLandmarks, ...]:
    hands: list[HandLandmarks] = []
    for index, landmarks in enumerate(result.hand_landmarks):
        categories = result.handedness[index] if index < len(result.handedness) else ()
        hands.append(_map_hand(landmarks=landmarks, categories=categories))
    return tuple(hands)


class MediaPipeTasksFacade:
    """Fachada real sobre mediapipe.tasks.python.vision.HandLandmarker."""

    def __init__(self, config: HandsConfig) -> None:
        self._config = config
        self._landmarker: _LandmarkerLike | None = None

    def open(self) -> None:
        """Crea el HandLandmarker en modo VIDEO.

        Raises:
            HandTrackerError: si ya estaba abierto o el modelo no puede cargarse.
        """
        if self._landmarker is not None:
            msg = "El detector de MediaPipe ya esta abierto."
            raise HandTrackerError(msg)

        model_path = Path(self._config.model_path)
        if not model_path.is_file():
            msg = f"No existe el modelo de manos: {model_path}"
            raise HandTrackerError(msg)

        try:
            self._landmarker = _create_landmarker(config=self._config, model_path=model_path)
        except (OSError, RuntimeError, ValueError) as exc:
            msg = f"No se pudo cargar el modelo de manos: {model_path}"
            raise HandTrackerError(msg) from exc

    def detect(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        timestamp_ms: int,
    ) -> tuple[HandLandmarks, ...]:
        """Detecta manos en el fotograma BGR.

        Raises:
            HandTrackerError: si se llama antes de open() o si el runtime de
                MediaPipe/cv2 falla durante la deteccion.
        """
        if self._landmarker is None:
            msg = "El detector de MediaPipe no esta abierto: llama a open() antes de detect()."
            raise HandTrackerError(msg)

        try:
            image = _to_mp_image(frame_bgr)
            result = self._landmarker.detect_for_video(image, timestamp_ms)
        except (cv2.error, RuntimeError, ValueError) as exc:
            msg = "Fallo la deteccion de manos en MediaPipe."
            raise HandTrackerError(msg) from exc
        return _map_result(result)

    def close(self) -> None:
        """Cierra el HandLandmarker si esta abierto."""
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None


class MediaPipeHandTracker(HandTracker):
    """Detecta manos con MediaPipe Tasks; la fachada es inyectable para tests."""

    def __init__(
        self,
        config: HandsConfig,
        facade_factory: Callable[[HandsConfig], HandDetectorFacade] | None = None,
    ) -> None:
        self._config = config
        self._facade_factory = facade_factory or MediaPipeTasksFacade
        self._facade: HandDetectorFacade | None = None

    def open(self) -> None:
        """Crea y abre la fachada del detector.

        Raises:
            HandTrackerError: si el detector ya estaba abierto o la fachada fallo.
        """
        if self._facade is not None:
            msg = "El detector de manos ya esta abierto."
            raise HandTrackerError(msg)

        facade = self._facade_factory(self._config)
        facade.open()
        self._facade = facade

    def detect(self, frame: Frame) -> tuple[HandLandmarks, ...]:
        """Detecta las manos del fotograma.

        Raises:
            HandTrackerError: si se llama sin haber abierto el detector.
        """
        if self._facade is None:
            msg = "El detector de manos no esta abierto: llama a open() antes de detect()."
            raise HandTrackerError(msg)

        timestamp_ms = int(frame.timestamp * MILLISECONDS_PER_SECOND)
        return self._facade.detect(frame_bgr=frame.data, timestamp_ms=timestamp_ms)

    def close(self) -> None:
        """Cierra la fachada; es idempotente."""
        if self._facade is not None:
            self._facade.close()
            self._facade = None

    def __enter__(self) -> "MediaPipeHandTracker":
        self.open()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
