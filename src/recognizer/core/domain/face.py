"""Rostros enrolados y sesion facial (dominio puro).

El enrolamiento captura varias muestras del rostro en distintos angulos y las
promedia en un embedding; el login compara el embedding observado con los
enrolados por distancia coseno y confirma la identidad con debounce.
Sin numpy ni infraestructura: los embeddings son tuplas de flotantes.
"""

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from recognizer.core.constants import (
    DEFAULT_ENROLLMENT_SAMPLES,
    DEFAULT_FACE_CENTER_TOLERANCE,
    DEFAULT_FACE_CONFIRM_FRAMES,
    DEFAULT_FACE_MATCH_THRESHOLD,
    DEFAULT_FACE_RELEASE_FRAMES,
    DEFAULT_MAX_FACE_WIDTH_RATIO,
    DEFAULT_MIN_FACE_SHARPNESS,
    DEFAULT_MIN_FACE_WIDTH_RATIO,
    FACE_ID_PREFIX,
    FACE_ID_WIDTH,
    FACE_MAX_COSINE_DISTANCE,
    MIN_VECTOR_NORM,
)
from recognizer.core.domain.identity import Role
from recognizer.core.errors import ConfigError

FaceEmbedding = tuple[float, ...]


class FacePoseStep(StrEnum):
    """Angulo pedido durante el enrolamiento."""

    FRONT = "frente"
    LEFT = "izquierda"
    RIGHT = "derecha"
    UP = "arriba"
    DOWN = "abajo"


class CaptureGuidance(StrEnum):
    """Guia para colocar la cara ante la camara."""

    CENTER_FACE = "centra la cara en el encuadre"
    MOVE_CLOSER = "acercate a la camara"
    MOVE_FARTHER = "alejate de la camara"
    HOLD_STILL = "quedate quieto"
    TURN_LEFT = "gira levemente a la izquierda"
    TURN_RIGHT = "gira levemente a la derecha"
    LOOK_UP = "mira levemente arriba"
    LOOK_DOWN = "mira levemente abajo"
    GOOD = "bien, manten la posicion"


@dataclass(frozen=True, slots=True)
class FaceBox:
    """Caja facial normalizada respecto al fotograma (rango 0..1)."""

    x_min: float
    y_min: float
    x_max: float
    y_max: float
    confidence: float

    def __post_init__(self) -> None:
        for name, value in (
            ("x_min", self.x_min),
            ("y_min", self.y_min),
            ("x_max", self.x_max),
            ("y_max", self.y_max),
        ):
            if not 0.0 <= value <= 1.0:
                msg = f"La caja facial requiere 0 <= {name} <= 1 (llego {value})."
                raise ConfigError(msg)
        if self.x_min >= self.x_max:
            msg = "La caja facial requiere x_min < x_max."
            raise ConfigError(msg)
        if self.y_min >= self.y_max:
            msg = "La caja facial requiere y_min < y_max."
            raise ConfigError(msg)
        if not 0.0 <= self.confidence <= 1.0:
            msg = f"La confianza requiere 0 <= confidence <= 1 (llego {self.confidence})."
            raise ConfigError(msg)

    @property
    def width(self) -> float:
        """Ancho normalizado de la caja."""
        return self.x_max - self.x_min

    @property
    def center_x(self) -> float:
        """Coordenada X normalizada del centro."""
        return (self.x_min + self.x_max) / 2

    @property
    def center_y(self) -> float:
        """Coordenada Y normalizada del centro."""
        return (self.y_min + self.y_max) / 2


@dataclass(frozen=True, slots=True)
class FaceObservation:
    """Una cara vista en un fotograma: embedding, caja y nitidez."""

    embedding: FaceEmbedding
    box: FaceBox
    sharpness: float


@dataclass(frozen=True, slots=True)
class EnrolledFace:
    """Rostro enrolado: identidad, embedding promedio, muestras, rol y foto.

    ``role``, ``preview`` y ``password_hash`` van al final con default para
    migrar: los enrolados antes de la etapa 15b se leen como operator, los
    anteriores a la 15c sin foto y los anteriores a la 15d sin clave de
    respaldo. ``preview`` es el nombre de archivo de la foto de enrolamiento
    (``F-0001.png``) dentro del almacen; ``""`` si no hay foto.
    ``password_hash`` es el hash PBKDF2 de la clave de respaldo (login sin
    camara) o ``""`` si el rostro no tiene clave.
    """

    face_id: str
    name: str
    embedding: FaceEmbedding
    samples: int
    created_at: str
    role: Role = Role.OPERATOR
    preview: str = ""
    password_hash: str = ""


@dataclass(frozen=True, slots=True)
class FaceMatch:
    """Mejor coincidencia de una observacion contra los enrolados."""

    face: EnrolledFace | None
    distance: float
    accepted: bool


@dataclass(frozen=True, slots=True)
class EnrollmentPoseSpec:
    """Un paso del enrolamiento: angulo pedido y su instruccion."""

    step: FacePoseStep
    prompt: str


ENROLLMENT_STEPS: tuple[EnrollmentPoseSpec, ...] = (
    EnrollmentPoseSpec(step=FacePoseStep.FRONT, prompt="Mira al frente"),
    EnrollmentPoseSpec(step=FacePoseStep.LEFT, prompt="Gira levemente a la izquierda"),
    EnrollmentPoseSpec(step=FacePoseStep.RIGHT, prompt="Gira levemente a la derecha"),
    EnrollmentPoseSpec(step=FacePoseStep.UP, prompt="Mira levemente arriba"),
    EnrollmentPoseSpec(step=FacePoseStep.DOWN, prompt="Mira levemente abajo"),
)

_FACE_CENTER = 0.5


def l2_normalize(vec: FaceEmbedding) -> FaceEmbedding:
    """Normaliza un vector a norma unitaria; el vector nulo queda en ceros."""
    norm = math.sqrt(sum(value * value for value in vec))
    if norm <= MIN_VECTOR_NORM:
        return tuple(0.0 for _ in vec)
    return tuple(value / norm for value in vec)


def mean_embedding(vecs: tuple[FaceEmbedding, ...]) -> FaceEmbedding:
    """Promedia embeddings y normaliza el resultado.

    Raises:
        ValueError: si no hay vectores o tienen dimensiones distintas.
    """
    if not vecs:
        msg = "Se requiere al menos un embedding para promediar."
        raise ValueError(msg)
    dimension = len(vecs[0])
    for vec in vecs:
        if len(vec) != dimension:
            msg = "Los embeddings deben tener la misma dimension."
            raise ValueError(msg)
    count = len(vecs)
    mean = tuple(sum(vec[index] for vec in vecs) / count for index in range(dimension))
    return l2_normalize(mean)


def cosine_distance(first: FaceEmbedding, second: FaceEmbedding) -> float:
    """Distancia coseno (0 = identicos); vectores nulos dan la maxima."""
    if len(first) != len(second):
        msg = "Los embeddings deben tener la misma dimension."
        raise ValueError(msg)
    norm_first = math.sqrt(sum(value * value for value in first))
    norm_second = math.sqrt(sum(value * value for value in second))
    if norm_first <= MIN_VECTOR_NORM or norm_second <= MIN_VECTOR_NORM:
        return FACE_MAX_COSINE_DISTANCE
    similarity = sum(a * b for a, b in zip(first, second, strict=True)) / (norm_first * norm_second)
    clamped = max(-1.0, min(1.0, similarity))
    return max(0.0, min(FACE_MAX_COSINE_DISTANCE, 1.0 - clamped))


def face_width_ratio(box: FaceBox) -> float:
    """Fraccion del ancho del fotograma que ocupa la cara."""
    return box.width


def assess_capture(
    box: FaceBox,
    sharpness: float,
    *,
    min_width: float = DEFAULT_MIN_FACE_WIDTH_RATIO,
    max_width: float = DEFAULT_MAX_FACE_WIDTH_RATIO,
    min_sharpness: float = DEFAULT_MIN_FACE_SHARPNESS,
    center_tolerance: float = DEFAULT_FACE_CENTER_TOLERANCE,
) -> CaptureGuidance:
    """Guia de captura segun tamano, nitidez y centrado de la cara."""
    width = face_width_ratio(box)
    if width < min_width:
        return CaptureGuidance.MOVE_CLOSER
    if width > max_width:
        return CaptureGuidance.MOVE_FARTHER
    if sharpness < min_sharpness:
        return CaptureGuidance.HOLD_STILL
    off_center = (
        abs(box.center_x - _FACE_CENTER) > center_tolerance
        or abs(box.center_y - _FACE_CENTER) > center_tolerance
    )
    if off_center:
        return CaptureGuidance.CENTER_FACE
    return CaptureGuidance.GOOD


def next_face_id(existing: Mapping[str, object] | Iterable[str]) -> str:
    """Siguiente identificador secuencial ``F-%04d`` tras el maximo existente."""
    names: Iterable[str] = existing.keys() if isinstance(existing, Mapping) else existing
    highest = 0
    for name in names:
        if not name.startswith(FACE_ID_PREFIX):
            continue
        suffix = name[len(FACE_ID_PREFIX) :]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f"{FACE_ID_PREFIX}{highest + 1:0{FACE_ID_WIDTH}d}"


class EnrollmentBuilder:
    """Acumula muestras validas hasta completar el enrolamiento."""

    def __init__(
        self,
        *,
        samples_required: int = DEFAULT_ENROLLMENT_SAMPLES,
        min_width: float = DEFAULT_MIN_FACE_WIDTH_RATIO,
        max_width: float = DEFAULT_MAX_FACE_WIDTH_RATIO,
        min_sharpness: float = DEFAULT_MIN_FACE_SHARPNESS,
    ) -> None:
        if samples_required < 1:
            msg = f"El enrolamiento requiere samples_required >= 1 (llego {samples_required})."
            raise ConfigError(msg)
        if not 0.0 <= min_width < max_width <= 1.0:
            msg = "El enrolamiento requiere 0 <= min_width < max_width <= 1."
            raise ConfigError(msg)
        if min_sharpness < 0:
            msg = f"La nitidez minima requiere min_sharpness >= 0 (llego {min_sharpness})."
            raise ConfigError(msg)
        self._samples_required = samples_required
        self._min_width = min_width
        self._max_width = max_width
        self._min_sharpness = min_sharpness
        self._samples: list[FaceEmbedding] = []

    @property
    def accepted(self) -> int:
        """Muestras validas acumuladas."""
        return len(self._samples)

    @property
    def is_complete(self) -> bool:
        """Indica si ya hay suficientes muestras para construir el rostro."""
        return len(self._samples) >= self._samples_required

    def current_step(self) -> EnrollmentPoseSpec:
        """Paso de angulo sugerido segun las muestras aceptadas."""
        return ENROLLMENT_STEPS[len(self._samples) % len(ENROLLMENT_STEPS)]

    def add(self, observation: FaceObservation) -> CaptureGuidance | None:
        """Valida una observacion; ``None`` si se acepto, guia si debe repetirse."""
        if self.is_complete:
            return None
        guidance = assess_capture(
            observation.box,
            observation.sharpness,
            min_width=self._min_width,
            max_width=self._max_width,
            min_sharpness=self._min_sharpness,
        )
        match guidance:
            case CaptureGuidance.GOOD:
                self._samples.append(observation.embedding)
                return None
            case _:
                return guidance

    def build(
        self,
        face_id: str,
        name: str,
        *,
        role: Role = Role.OPERATOR,
        password_hash: str = "",
    ) -> EnrolledFace:
        """Construye el rostro enrolado con el promedio de las muestras.

        ``password_hash`` es el hash de la clave de respaldo (``""`` si no se
        asigna, p. ej. al re-enrolar conservando la clave actual).

        Raises:
            ValueError: si faltan muestras o el nombre esta vacio.
        """
        if not self.is_complete:
            msg = f"Faltan muestras: {len(self._samples)}/{self._samples_required}."
            raise ValueError(msg)
        if not name.strip():
            msg = "El enrolamiento requiere un nombre no vacio."
            raise ValueError(msg)
        embedding = mean_embedding(tuple(self._samples))
        created_at = datetime.now(UTC).isoformat()
        return EnrolledFace(
            face_id=face_id,
            name=name.strip(),
            embedding=embedding,
            samples=len(self._samples),
            created_at=created_at,
            role=role,
            password_hash=password_hash,
        )


class FaceMatcher:
    """Compara un embedding contra los enrolados por distancia coseno."""

    def __init__(self, threshold: float = DEFAULT_FACE_MATCH_THRESHOLD) -> None:
        if threshold < 0:
            msg = f"El matching requiere threshold >= 0 (llego {threshold})."
            raise ConfigError(msg)
        self._threshold = threshold

    def identify(self, query: FaceEmbedding, enrolled: tuple[EnrolledFace, ...]) -> FaceMatch:
        """Devuelve la mejor coincidencia; acepta si no supera el umbral."""
        best: EnrolledFace | None = None
        best_distance = FACE_MAX_COSINE_DISTANCE
        for face in enrolled:
            distance = cosine_distance(query, face.embedding)
            if distance < best_distance:
                best_distance = distance
                best = face
        if best is None:
            return FaceMatch(face=None, distance=FACE_MAX_COSINE_DISTANCE, accepted=False)
        return FaceMatch(
            face=best, distance=best_distance, accepted=best_distance <= self._threshold
        )


class LoginDebouncer:
    """Confirma la identidad con debounce: exige rachas para entrar y salir."""

    def __init__(
        self,
        *,
        confirm_frames: int = DEFAULT_FACE_CONFIRM_FRAMES,
        release_frames: int = DEFAULT_FACE_RELEASE_FRAMES,
    ) -> None:
        if confirm_frames < 1:
            msg = f"La confirmacion requiere confirm_frames >= 1 (llego {confirm_frames})."
            raise ConfigError(msg)
        if release_frames < 1:
            msg = f"La liberacion requiere release_frames >= 1 (llego {release_frames})."
            raise ConfigError(msg)
        self._confirm_frames = confirm_frames
        self._release_frames = release_frames
        self._candidate: EnrolledFace | None = None
        self._candidate_frames = 0
        self._absent_frames = 0
        self._stable: EnrolledFace | None = None

    def update(self, match: FaceMatch) -> EnrolledFace | None:
        """Actualiza con la coincidencia del fotograma; identidad estable o ``None``."""
        if match.accepted and match.face is not None:
            self._absent_frames = 0
            if self._candidate is None or self._candidate.face_id != match.face.face_id:
                self._candidate = match.face
                self._candidate_frames = 1
            else:
                self._candidate_frames += 1
            if self._candidate_frames >= self._confirm_frames:
                self._stable = match.face
            return self._stable
        self._candidate_frames = 0
        self._candidate = None
        self._absent_frames += 1
        if self._absent_frames >= self._release_frames:
            self._stable = None
        return self._stable

    def reset(self) -> None:
        """Limpia la identidad estable y las rachas."""
        self._candidate = None
        self._candidate_frames = 0
        self._absent_frames = 0
        self._stable = None
