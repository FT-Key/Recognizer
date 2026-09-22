"""Deteccion de somnolencia (dominio puro).

Un ``DrowsinessDetector`` evalua si alguna persona esta somnoliente
combinando pose corporal (YOLO pose) y landmarks faciales (MediaPipe Face Mesh).
La deteccion combina cinco senales:

**Senales de pose (YOLO pose):**
1. **Cabeza caida** (``head_droop``): la posicion Y de la nariz respecto al
   centro de los hombros. Cuando la cabeza se inclina hacia adelante/abajo,
   la nariz baja mas que los hombros.

2. **Cabeceo** (``nod_amplitude``): oscilacion vertical de la nariz en una
   ventana de ``nodding_window`` fotogramas. Si la amplitud (max - min) supera
   un umbral, la persona esta cabeceando (senal de somnolencia).

**Senales faciales (MediaPipe Face Mesh):**
3. **Ojos cerrados** (``ear``): Eye Aspect Ratio. Un ojo abierto tiene EAR ~0.3,
   un ojo cerrado tiene EAR ~0.05. Si EAR promedio < ``ear_threshold`` por
   ``eye_close_frames`` fotogramas consecutivos, es somnolencia.

4. **Bostezo** (``mar``): Mouth Aspect Ratio. Una boca cerrada tiene MAR ~0.02,
   un bostezo tiene MAR > 0.5. Si MAR > ``mar_threshold`` por
   ``yawn_frames`` fotogramas consecutivos, es somnolencia.

Las senales de pose y las faciales son independientes: si la camara no ve el
cuerpo (p. ej. solo el rostro en primer plano) la somnolencia se detecta igual
por EAR/MAR. Una senal se confirma cuando supera su umbral durante
``confirm_frames`` fotogramas consecutivos; la alerta se libera tras
``release_frames`` fotogramas sin senales de somnolencia.
"""

from collections import deque
from dataclasses import dataclass

from recognizer.core.domain.face_landmarks import FaceMeshResult
from recognizer.core.domain.pose import Pose, PoseKeypoint
from recognizer.core.errors import ConfigError


@dataclass(frozen=True, slots=True)
class DrowsinessMetrics:
    """Metricas extraidas de un frame para evaluar somnolencia."""

    head_droop: float | None = None
    nod_amplitude: float | None = None
    ear_avg: float | None = None
    mar: float | None = None

    def any_available(self) -> bool:
        """Indica si al menos una metrica pudo calcularse."""
        return any(
            value is not None
            for value in (self.head_droop, self.nod_amplitude, self.ear_avg, self.mar)
        )


@dataclass(frozen=True, slots=True)
class DrowsinessSnapshot:
    """Estado confirmado de la deteccion de somnolencia tras el debounce."""

    active: bool
    drowsy_count: int = 0
    people: int = 0
    ear_avg: float | None = None
    mar: float | None = None
    head_droop: float | None = None
    nod_amplitude: float | None = None


def _shoulder_center(pose: Pose, min_keypoint_confidence: float) -> float | None:
    """Centro Y de los hombros o ``None`` si no hay suficientes puntos."""
    left = pose.keypoint(PoseKeypoint.LEFT_SHOULDER)
    right = pose.keypoint(PoseKeypoint.RIGHT_SHOULDER)
    if left is None or right is None:
        return None
    if left.confidence < min_keypoint_confidence or right.confidence < min_keypoint_confidence:
        return None
    return (left.y + right.y) / 2


def _nose_y(pose: Pose, min_keypoint_confidence: float) -> float | None:
    """Posicion Y de la nariz o ``None`` si no es fiable."""
    keypoint = pose.keypoint(PoseKeypoint.NOSE)
    if keypoint is None or keypoint.confidence < min_keypoint_confidence:
        return None
    return keypoint.y


def _body_center(pose: Pose, min_keypoint_confidence: float) -> float | None:
    """Centro Y del torso (hombros + caderas) o ``None`` si falta."""
    points_y: list[float] = []
    for name in (
        PoseKeypoint.LEFT_SHOULDER,
        PoseKeypoint.RIGHT_SHOULDER,
        PoseKeypoint.LEFT_HIP,
        PoseKeypoint.RIGHT_HIP,
    ):
        kp = pose.keypoint(name)
        if kp is not None and kp.confidence >= min_keypoint_confidence:
            points_y.append(kp.y)
    if not points_y:
        return None
    return sum(points_y) / len(points_y)


def measure_drowsiness(
    pose: Pose | None,
    *,
    min_keypoint_confidence: float,
    nod_amplitude: float | None = None,
    face: FaceMeshResult | None = None,
) -> DrowsinessMetrics:
    """Calcula las metricas de somnolencia disponibles.

    ``pose`` es opcional: si la camara no ve el cuerpo (p. ej. solo la cara),
    igual se evaluan las senales faciales (ojos cerrados, bostezo).
    """
    head_droop: float | None = None
    if pose is not None:
        nose = _nose_y(pose, min_keypoint_confidence)
        shoulder = _shoulder_center(pose, min_keypoint_confidence)
        if nose is not None and shoulder is not None:
            head_droop = nose - shoulder

    return DrowsinessMetrics(
        head_droop=head_droop,
        nod_amplitude=nod_amplitude,
        ear_avg=face.ear_avg if face is not None else None,
        mar=face.mar if face is not None else None,
    )


class DrowsinessDetector:
    """Detecta somnolencia con debounce por fotogramas.

    Evalua cada frame combinando pose corporal y face mesh, y marca somnolencia
    cuando la cabeza caida, el cabeceo, los ojos cerrados o un bostezo superan
    sus umbrales durante ``confirm_frames`` fotogramas consecutivos.
    """

    def __init__(
        self,
        *,
        min_keypoint_confidence: float,
        head_droop_threshold: float,
        nod_amplitude_threshold: float,
        nodding_window: int,
        ear_threshold: float,
        eye_close_frames: int,
        mar_threshold: float,
        yawn_frames: int,
        confirm_frames: int,
        release_frames: int,
    ) -> None:
        if confirm_frames < 1:
            msg = f"La confirmacion requiere confirm_frames >= 1 (llego {confirm_frames})."
            raise ConfigError(msg)
        if release_frames < 1:
            msg = f"La liberacion requiere release_frames >= 1 (llego {release_frames})."
            raise ConfigError(msg)
        if nodding_window < 1:
            msg = f"La ventana de cabeceo requiere nodding_window >= 1 (llego {nodding_window})."
            raise ConfigError(msg)
        if eye_close_frames < 1:
            msg = f"La ventana de ojos requiere eye_close_frames >= 1 (llego {eye_close_frames})."
            raise ConfigError(msg)
        if yawn_frames < 1:
            msg = f"La ventana de bostezo requiere yawn_frames >= 1 (llego {yawn_frames})."
            raise ConfigError(msg)
        self._min_keypoint_confidence = min_keypoint_confidence
        self._head_droop_threshold = head_droop_threshold
        self._nod_amplitude_threshold = nod_amplitude_threshold
        self._nodding_window = nodding_window
        self._ear_threshold = ear_threshold
        self._eye_close_frames = eye_close_frames
        self._mar_threshold = mar_threshold
        self._yawn_frames = yawn_frames
        self._confirm_frames = confirm_frames
        self._release_frames = release_frames
        self._up_frames = 0
        self._down_frames = 0
        self._active = False
        self._nose_history: deque[float] = deque(maxlen=nodding_window)
        self._ear_history: deque[float] = deque(maxlen=eye_close_frames)
        self._mar_history: deque[float] = deque(maxlen=yawn_frames)

    def _compute_nod_amplitude(self, nose_y: float) -> float:
        """Calcula la amplitud de oscilacion de la nariz en la ventana."""
        self._nose_history.append(nose_y)
        if len(self._nose_history) < 2:
            return 0.0
        return max(self._nose_history) - min(self._nose_history)

    def _is_drowsy(self, metrics: DrowsinessMetrics) -> bool:
        """Evalua si las metricas indican somnolencia."""
        if metrics.head_droop is not None and metrics.head_droop >= self._head_droop_threshold:
            return True
        if (
            metrics.nod_amplitude is not None
            and metrics.nod_amplitude >= self._nod_amplitude_threshold
        ):
            return True

        # Ojos cerrados: EAR bajo por varios fotogramas consecutivos
        if metrics.ear_avg is not None:
            self._ear_history.append(metrics.ear_avg)
            if len(self._ear_history) >= self._eye_close_frames:
                recent_ears = list(self._ear_history)[-self._eye_close_frames :]
                if all(ear < self._ear_threshold for ear in recent_ears):
                    return True

        # Bostezo: MAR alto por varios fotogramas consecutivos
        if metrics.mar is not None:
            self._mar_history.append(metrics.mar)
            if len(self._mar_history) >= self._yawn_frames:
                recent_mars = list(self._mar_history)[-self._yawn_frames :]
                if all(mar > self._mar_threshold for mar in recent_mars):
                    return True

        return False

    def update(
        self,
        poses: tuple[Pose, ...],
        faces: tuple[FaceMeshResult, ...] = (),
    ) -> DrowsinessSnapshot:
        """Actualiza el estado con las posturas y landmarks faciales del fotograma.

        Las senales de pose (cabeza caida, cabeceo) y las faciales (ojos cerrados,
        bostezo) se evaluan de forma independiente: si la camara no ve el cuerpo
        pero si la cara, la somnolencia se detecta igual por EAR/MAR.
        """
        drowsy = 0

        primary_pose = poses[0] if poses else None
        primary_face = faces[0] if faces else None

        nod_amp: float | None = None
        if primary_pose is not None:
            primary_nose = _nose_y(primary_pose, self._min_keypoint_confidence)
            if primary_nose is not None:
                nod_amp = self._compute_nod_amplitude(primary_nose)

        primary_metrics: DrowsinessMetrics | None = None

        if poses:
            for i, pose in enumerate(poses):
                face = primary_face if i == 0 else None
                metrics = measure_drowsiness(
                    pose,
                    min_keypoint_confidence=self._min_keypoint_confidence,
                    nod_amplitude=nod_amp,
                    face=face,
                )
                if primary_metrics is None:
                    primary_metrics = metrics
                if self._is_drowsy(metrics):
                    drowsy += 1
        else:
            # Sin pose (la camara no ve el cuerpo): evaluar solo la cara.
            metrics = measure_drowsiness(
                None,
                min_keypoint_confidence=self._min_keypoint_confidence,
                face=primary_face,
            )
            primary_metrics = metrics
            if self._is_drowsy(metrics):
                drowsy += 1

        if drowsy > 0:
            self._up_frames += 1
            self._down_frames = 0
            if self._up_frames >= self._confirm_frames:
                self._active = True
        else:
            self._down_frames += 1
            self._up_frames = 0
            if self._down_frames >= self._release_frames:
                self._active = False

        people = len(poses) if poses else len(faces)
        return DrowsinessSnapshot(
            active=self._active,
            drowsy_count=drowsy,
            people=people,
            ear_avg=primary_metrics.ear_avg if primary_metrics else None,
            mar=primary_metrics.mar if primary_metrics else None,
            head_droop=primary_metrics.head_droop if primary_metrics else None,
            nod_amplitude=primary_metrics.nod_amplitude if primary_metrics else None,
        )

    def reset(self) -> None:
        """Limpia el estado del debounce y del historial."""
        self._up_frames = 0
        self._down_frames = 0
        self._active = False
        self._nose_history.clear()
        self._ear_history.clear()
        self._mar_history.clear()
