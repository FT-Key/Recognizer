"""Dominio de landmarks faciales (468 puntos MediaPipe Face Mesh).

Define los tipos puros para los 468 landmarks del rostro, los puntos clave
para calcular EAR (Eye Aspect Ratio) y MAR (Mouth Aspect Ratio), y las
funciones de calculo de ratios faciales.
"""

import math
from dataclasses import dataclass

# --- Coordenadas 3D de un landmark facial ---


@dataclass(frozen=True, slots=True)
class FaceLandmark3D:
    """Un punto 3D del rostro en coordenadas normalizadas (0..1)."""

    x: float
    y: float
    z: float


# --- Indexes de MediaPipe Face Mesh para ojos, boca, nariz ---
# Basado en la topologia de MediaPipe Face Mesh (468 landmarks).

# Ojo izquierdo (6 puntos para EAR)
LEFT_EYE_IDXS: tuple[int, ...] = (33, 160, 158, 133, 153, 144)

# Ojo derecho (6 puntos para EAR)
RIGHT_EYE_IDXS: tuple[int, ...] = (362, 385, 387, 263, 373, 380)

# Boca (6 puntos para MAR)
MOUTH_IDXS: tuple[int, ...] = (61, 0, 267, 291, 375, 321)

# Puntos verticales del ojo izquierdo (par superior e inferior)
LEFT_EYE_VERTICAL: tuple[tuple[int, int], ...] = ((159, 145), (153, 144))

# Puntos verticales del ojo derecho (par superior e inferior)
RIGHT_EYE_VERTICAL: tuple[tuple[int, int], ...] = ((386, 374), (373, 380))

# Puntos horizontales del ojo izquierdo (esquina interna y externa)
LEFT_EYE_HORIZONTAL: tuple[int, int] = (33, 133)

# Puntos horizontales del ojo derecho (esquina interna y externa)
RIGHT_EYE_HORIZONTAL: tuple[int, int] = (362, 263)

# Puntos verticales de la boca (par superior e inferior)
MOUTH_VERTICAL: tuple[tuple[int, int], ...] = ((37, 0), (267, 321))


# --- Funciones de calculo de ratios ---


def _distance(a: FaceLandmark3D, b: FaceLandmark3D) -> float:
    """Distancia euclidea entre dos puntos 3D."""
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


def compute_eye_aspect_ratio(
    landmarks: tuple[FaceLandmark3D, ...],
    vertical_pairs: tuple[tuple[int, int], ...],
    horizontal: tuple[int, int],
) -> float:
    """Calcula el Eye Aspect Ratio (EAR) para un ojo.

    EAR = (||p2-p6|| + ||p3-pp5||) / (2 * ||p1-p4||)

    Donde p1,p4 son los puntos horizontales (esquinas) y p2,p3,p5,p6 son
    los puntos verticales (par superior e inferior).

    Un ojo abierto tiene EAR ~0.3. Un ojo cerrado tiene EAR ~0.05.
    """
    h1 = _distance(landmarks[horizontal[0]], landmarks[horizontal[1]])
    if h1 < 1e-6:
        return 0.0
    v_sum = sum(_distance(landmarks[pair[0]], landmarks[pair[1]]) for pair in vertical_pairs)
    return v_sum / (2.0 * h1)


def compute_mouth_aspect_ratio(
    landmarks: tuple[FaceLandmark3D, ...],
    vertical_pairs: tuple[tuple[int, int], ...],
    horizontal: tuple[int, int],
) -> float:
    """Calcula el Mouth Aspect Ratio (MAR) para la boca.

    MAR = sum(||p_i - p_j|| para pares verticales) / (2 * ||p_left - p_right||)

    Una boca cerrada tiene MAR ~0.02. Un bostezo tiene MAR > 0.5.
    """
    h1 = _distance(landmarks[horizontal[0]], landmarks[horizontal[1]])
    if h1 < 1e-6:
        return 0.0
    v_sum = sum(_distance(landmarks[pair[0]], landmarks[pair[1]]) for pair in vertical_pairs)
    return v_sum / (2.0 * h1)


# --- Dataclasses para el resultado ---


@dataclass(frozen=True, slots=True)
class FaceMeshResult:
    """Resultado del Face Mesh para un solo rostro."""

    landmarks: tuple[FaceLandmark3D, ...]
    ear_left: float
    ear_right: float
    mar: float

    @property
    def ear_avg(self) -> float:
        """EAR promedio de ambos ojos."""
        return (self.ear_left + self.ear_right) / 2.0


def compute_face_mesh_metrics(
    landmarks: tuple[FaceLandmark3D, ...],
) -> FaceMeshResult:
    """Calcula EAR y MAR a partir de los 468 landmarks de un rostro."""
    ear_left = compute_eye_aspect_ratio(landmarks, LEFT_EYE_VERTICAL, LEFT_EYE_HORIZONTAL)
    ear_right = compute_eye_aspect_ratio(landmarks, RIGHT_EYE_VERTICAL, RIGHT_EYE_HORIZONTAL)
    mar = compute_mouth_aspect_ratio(landmarks, MOUTH_VERTICAL, MOUTH_HORIZONTAL)
    return FaceMeshResult(
        landmarks=landmarks,
        ear_left=ear_left,
        ear_right=ear_right,
        mar=mar,
    )


MOUTH_HORIZONTAL: tuple[int, int] = (61, 291)
