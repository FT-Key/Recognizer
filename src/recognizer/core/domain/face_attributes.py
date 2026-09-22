"""Edad y genero estimados por rostro (dominio puro).

Empareja las caras de fotogramas consecutivos por IoU y suaviza la edad con la
mediana y el genero con voto mayoritario, para evitar el parpadeo tipico del
estimador. Sin numpy ni infraestructura: las cajas son objetos de valor.
"""

from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum

from recognizer.core.constants import (
    DEFAULT_GENDER_AGE_SMOOTHING_WINDOW,
    GENDER_AGE_IOU_THRESHOLD,
    GENDER_AGE_MAX_MISSES,
    MAX_ESTIMATED_AGE,
    MIN_ESTIMATED_AGE,
)
from recognizer.core.domain.face import FaceBox
from recognizer.core.errors import ConfigError


class FaceGender(StrEnum):
    """Genero estimado por el modelo (desconocido si no lo informa)."""

    FEMALE = "F"
    MALE = "M"
    UNKNOWN = "?"


@dataclass(frozen=True, slots=True)
class FaceAttributes:
    """Edad y genero estimados para la caja de un rostro."""

    box: FaceBox
    age: int
    gender: FaceGender

    def __post_init__(self) -> None:
        if not MIN_ESTIMATED_AGE <= self.age <= MAX_ESTIMATED_AGE:
            msg = (
                f"La edad estimada requiere {MIN_ESTIMATED_AGE} <= age <= "
                f"{MAX_ESTIMATED_AGE} (llego {self.age})."
            )
            raise ConfigError(msg)


def _box_area(box: FaceBox) -> float:
    """Area normalizada de una caja facial."""
    return box.width * (box.y_max - box.y_min)


def intersection_over_union(first: FaceBox, second: FaceBox) -> float:
    """IoU de dos cajas normalizadas; 0.0 si no se solapan."""
    x_min = max(first.x_min, second.x_min)
    y_min = max(first.y_min, second.y_min)
    x_max = min(first.x_max, second.x_max)
    y_max = min(first.y_max, second.y_max)
    if x_max <= x_min or y_max <= y_min:
        return 0.0
    intersection = (x_max - x_min) * (y_max - y_min)
    union = _box_area(first) + _box_area(second) - intersection
    if union <= 0.0:
        return 0.0
    return intersection / union


def _median_age(ages: deque[int]) -> int:
    """Mediana redondeada de las edades observadas."""
    if not ages:
        return MIN_ESTIMATED_AGE
    ordered = sorted(ages)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[middle]
    return round((ordered[middle - 1] + ordered[middle]) / 2)


def _majority_gender(genders: deque[FaceGender]) -> FaceGender:
    """Genero mas votado; en empate, el mas reciente."""
    if not genders:
        return FaceGender.UNKNOWN
    counts: dict[FaceGender, int] = {}
    for gender in genders:
        counts[gender] = counts.get(gender, 0) + 1
    top = max(counts.values())
    for gender in reversed(genders):
        if counts[gender] == top:
            return gender
    return FaceGender.UNKNOWN


@dataclass(slots=True, eq=False)
class _FaceSlot:
    """Historial de un rostro seguido entre fotogramas."""

    box: FaceBox
    ages: deque[int] = field(default_factory=deque)
    genders: deque[FaceGender] = field(default_factory=deque)
    misses: int = 0

    def observe(self, face: FaceAttributes, *, window: int) -> None:
        """Agrega la observacion y recorta el historial a la ventana."""
        self.box = face.box
        self.ages.append(face.age)
        self.genders.append(face.gender)
        while len(self.ages) > window:
            self.ages.popleft()
        while len(self.genders) > window:
            self.genders.popleft()

    def smoothed(self, *, box: FaceBox) -> FaceAttributes:
        """Cara suavizada: caja actual, mediana de edad y genero mayoritario."""
        return FaceAttributes(
            box=box,
            age=_median_age(self.ages),
            gender=_majority_gender(self.genders),
        )


class AgeGenderSmoother:
    """Suaviza edad y genero por rostro emparejando cajas por IoU.

    Cada cara de entrada se empareja con el slot libre de mayor IoU que iguale o
    supere
    ``iou_threshold``; las que no emparejan crean un slot nuevo y los slots sin
    observacion acumulan ausencias hasta purgarse. La edad devuelta es la
    mediana de su historial y el genero, el voto mayoritario (en empate, el
    valor mas reciente). Con ``window`` en 1 se devuelve el valor crudo.
    """

    def __init__(
        self,
        *,
        window: int = DEFAULT_GENDER_AGE_SMOOTHING_WINDOW,
        iou_threshold: float = GENDER_AGE_IOU_THRESHOLD,
        max_misses: int = GENDER_AGE_MAX_MISSES,
    ) -> None:
        if window < 1:
            msg = f"El suavizado requiere window >= 1 (llego {window})."
            raise ConfigError(msg)
        if not 0.0 <= iou_threshold <= 1.0:
            msg = f"El suavizado requiere 0 <= iou_threshold <= 1 (llego {iou_threshold})."
            raise ConfigError(msg)
        if max_misses < 1:
            msg = f"El suavizado requiere max_misses >= 1 (llego {max_misses})."
            raise ConfigError(msg)
        self._window = window
        self._iou_threshold = iou_threshold
        self._max_misses = max_misses
        self._slots: list[_FaceSlot] = []

    def update(self, faces: tuple[FaceAttributes, ...]) -> tuple[FaceAttributes, ...]:
        """Devuelve las caras suavizadas, en el mismo orden y tamano que la entrada."""
        assignments: list[_FaceSlot | None] = []
        used: list[_FaceSlot] = []
        available = list(self._slots)
        for face in faces:
            slot = self._best_slot(face.box, available)
            if slot is not None:
                available.remove(slot)
                used.append(slot)
            assignments.append(slot)
        smoothed: list[FaceAttributes] = []
        for face, slot in zip(faces, assignments, strict=True):
            target = slot
            if target is None:
                target = _FaceSlot(box=face.box)
                self._slots.append(target)
                used.append(target)
            target.observe(face, window=self._window)
            smoothed.append(target.smoothed(box=face.box))
        self._purge(used)
        return tuple(smoothed)

    def _best_slot(self, box: FaceBox, available: list[_FaceSlot]) -> _FaceSlot | None:
        """Slot libre con mayor IoU que iguale o supere el umbral; ``None`` si no hay."""
        best: _FaceSlot | None = None
        best_iou = self._iou_threshold
        for slot in available:
            iou = intersection_over_union(box, slot.box)
            if iou >= best_iou:
                best_iou = iou
                best = slot
        return best

    def _purge(self, used: list[_FaceSlot]) -> None:
        """Envejece los slots sin observacion y elimina los que superan las ausencias."""
        survivors: list[_FaceSlot] = []
        for slot in self._slots:
            if slot in used:
                slot.misses = 0
                survivors.append(slot)
                continue
            slot.misses += 1
            if slot.misses <= self._max_misses:
                survivors.append(slot)
        self._slots = survivors
