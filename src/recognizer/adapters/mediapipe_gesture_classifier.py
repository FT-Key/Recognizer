"""Adaptador de clasificacion de gestos basado en MediaPipe Tasks."""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.core.config import GestureConfig
from recognizer.core.constants import MILLISECONDS_PER_SECOND
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.gesture import (
    CANNED_GESTURE_LABELS,
    GESTURE_NONE,
    DetectedGesture,
    GestureId,
    GestureRecognition,
)
from recognizer.core.domain.hand import Handedness, HandLandmarks, Point
from recognizer.core.errors import GestureClassifierError
from recognizer.core.ports.gesture_classifier import GestureClassifier

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
    """Subconjunto de GestureRecognizerResult que usamos."""

    handedness: Sequence[Sequence[_CategoryLike]]
    hand_landmarks: Sequence[Sequence[_LandmarkLike]]
    gestures: Sequence[Sequence[_CategoryLike]]


class _GestureRecognizerLike(Protocol):
    """Subconjunto de GestureRecognizer que usamos (permite dobles en tests)."""

    def recognize_for_video(self, image: object, timestamp_ms: int) -> _ResultLike:
        """Clasifica una imagen con marca de tiempo."""
        ...

    def close(self) -> None:
        """Libera el recognizer."""
        ...


class GestureDetectorFacade(Protocol):
    """Contrato de la fachada que aisla MediaPipe del clasificador."""

    def open(self) -> None:
        """Prepara la fachada y carga el modelo."""
        ...

    def detect(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        timestamp_ms: int,
    ) -> GestureRecognition:
        """Clasifica manos y gestos en el fotograma BGR."""
        ...

    def close(self) -> None:
        """Libera los recursos de la fachada."""
        ...


def _create_recognizer(*, config: GestureConfig, model_path: Path) -> _GestureRecognizerLike:
    from mediapipe.tasks.python import BaseOptions, vision

    options = vision.GestureRecognizerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=config.max_hands,
        min_hand_detection_confidence=config.min_detection_confidence,
        min_hand_presence_confidence=config.min_presence_confidence,
        min_tracking_confidence=config.min_tracking_confidence,
    )
    # mediapipe no expone stubs: el cast fija la frontera tipada con la libreria.
    return cast("_GestureRecognizerLike", vision.GestureRecognizer.create_from_options(options))


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


def _map_gesture(
    *,
    categories: Sequence[_CategoryLike],
    handedness: Handedness,
    allowed_labels: frozenset[str],
) -> DetectedGesture:
    if categories:
        category = categories[0]
        label = category.category_name
        name = GestureId(label) if label in allowed_labels else GESTURE_NONE
        confidence = float(category.score)
    else:
        name = GESTURE_NONE
        confidence = MISSING_CATEGORY_CONFIDENCE
    return DetectedGesture(name=name, confidence=confidence, handedness=handedness)


def _map_result(
    result: _ResultLike,
    *,
    allowed_labels: frozenset[str],
) -> GestureRecognition:
    hands: list[HandLandmarks] = []
    detections: list[DetectedGesture] = []
    for index, landmarks in enumerate(result.hand_landmarks):
        hand_categories = result.handedness[index] if index < len(result.handedness) else ()
        hand = _map_hand(landmarks=landmarks, categories=hand_categories)
        gesture_categories = result.gestures[index] if index < len(result.gestures) else ()
        hands.append(hand)
        detections.append(
            _map_gesture(
                categories=gesture_categories,
                handedness=hand.handedness,
                allowed_labels=allowed_labels,
            )
        )
    return GestureRecognition(hands=tuple(hands), detections=tuple(detections))


class MediaPipeTasksGestureFacade:
    """Fachada real sobre mediapipe.tasks.python.vision.GestureRecognizer."""

    def __init__(self, config: GestureConfig) -> None:
        self._config = config
        self._recognizer: _GestureRecognizerLike | None = None
        self._allowed_labels: frozenset[str] = CANNED_GESTURE_LABELS

    def open(self) -> None:
        """Crea el GestureRecognizer en modo VIDEO.

        Raises:
            GestureClassifierError: si ya estaba abierto o el modelo no puede cargarse.
        """
        if self._recognizer is not None:
            msg = "El clasificador de MediaPipe ya esta abierto."
            raise GestureClassifierError(msg)

        model_path = Path(self._config.model_path)
        if not model_path.is_file():
            msg = f"No existe el modelo de gestos: {model_path}"
            raise GestureClassifierError(msg)

        try:
            self._recognizer = _create_recognizer(config=self._config, model_path=model_path)
        except (OSError, RuntimeError, ValueError) as exc:
            msg = f"No se pudo cargar el modelo de gestos: {model_path}"
            raise GestureClassifierError(msg) from exc
        self._allowed_labels = CANNED_GESTURE_LABELS | frozenset(self._config.custom_labels)

    def detect(
        self,
        *,
        frame_bgr: NDArray[np.uint8],
        timestamp_ms: int,
    ) -> GestureRecognition:
        """Clasifica manos y gestos en el fotograma BGR.

        Raises:
            GestureClassifierError: si se llama antes de open() o si el runtime de
                MediaPipe/cv2 falla durante la clasificacion.
        """
        if self._recognizer is None:
            msg = "El clasificador de MediaPipe no esta abierto: llama a open() antes."
            raise GestureClassifierError(msg)

        try:
            image = _to_mp_image(frame_bgr)
            result = self._recognizer.recognize_for_video(image, timestamp_ms)
        except (cv2.error, RuntimeError, ValueError) as exc:
            msg = "Fallo la clasificacion de gestos en MediaPipe."
            raise GestureClassifierError(msg) from exc
        return _map_result(result, allowed_labels=self._allowed_labels)

    def close(self) -> None:
        """Cierra el GestureRecognizer si esta abierto."""
        if self._recognizer is not None:
            self._recognizer.close()
            self._recognizer = None


class MediaPipeGestureClassifier(GestureClassifier):
    """Clasifica manos y gestos con MediaPipe Tasks; la fachada es inyectable."""

    def __init__(
        self,
        config: GestureConfig,
        facade_factory: Callable[[GestureConfig], GestureDetectorFacade] | None = None,
    ) -> None:
        self._config = config
        self._facade_factory = facade_factory or MediaPipeTasksGestureFacade
        self._facade: GestureDetectorFacade | None = None

    def open(self) -> None:
        """Crea y abre la fachada del clasificador.

        Raises:
            GestureClassifierError: si el clasificador ya estaba abierto o la fachada fallo.
        """
        if self._facade is not None:
            msg = "El clasificador de gestos ya esta abierto."
            raise GestureClassifierError(msg)

        facade = self._facade_factory(self._config)
        facade.open()
        self._facade = facade

    def classify(self, frame: Frame) -> GestureRecognition:
        """Clasifica las manos y gestos del fotograma.

        Raises:
            GestureClassifierError: si se llama sin haber abierto el clasificador.
        """
        if self._facade is None:
            msg = "El clasificador no esta abierto: llama a open() antes de classify()."
            raise GestureClassifierError(msg)

        timestamp_ms = int(frame.timestamp * MILLISECONDS_PER_SECOND)
        return self._facade.detect(frame_bgr=frame.data, timestamp_ms=timestamp_ms)

    def close(self) -> None:
        """Cierra la fachada; es idempotente."""
        if self._facade is not None:
            self._facade.close()
            self._facade = None

    def __enter__(self) -> "MediaPipeGestureClassifier":
        self.open()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
