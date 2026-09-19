"""Modelos de configuracion tipados y validados con pydantic."""

from typing import Annotated, Literal, Self
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from recognizer.core.constants import (
    DEFAULT_ACCESS_DIR,
    DEFAULT_ACTION_COOLDOWN_SECONDS,
    DEFAULT_BROWSER_DEBUGGING_PORT,
    DEFAULT_CAMERA_DEVICE_INDEX,
    DEFAULT_ENROLLMENT_SAMPLES,
    DEFAULT_FACE_CONFIDENCE,
    DEFAULT_FACE_CONFIRM_FRAMES,
    DEFAULT_FACE_DEFAULT_ROLE,
    DEFAULT_FACE_DET_SIZE,
    DEFAULT_FACE_MATCH_THRESHOLD,
    DEFAULT_FACE_MAX_INFERENCE_FPS,
    DEFAULT_FACE_PROCESS_EVERY_N_FRAMES,
    DEFAULT_FACE_RELEASE_FRAMES,
    DEFAULT_FACE_STORE_DIR,
    DEFAULT_FRAME_HEIGHT,
    DEFAULT_FRAME_WIDTH,
    DEFAULT_GESTURE_MODEL_PATH,
    DEFAULT_HAND_MODEL_PATH,
    DEFAULT_INTRUSION_ALERT_REPEAT_SECONDS,
    DEFAULT_INTRUSION_CONFIRM_FRAMES,
    DEFAULT_INTRUSION_RELEASE_FRAMES,
    DEFAULT_INTRUSION_ZONE_X_MAX,
    DEFAULT_INTRUSION_ZONE_X_MIN,
    DEFAULT_INTRUSION_ZONE_Y_MAX,
    DEFAULT_INTRUSION_ZONE_Y_MIN,
    DEFAULT_LINE_CONFIRM_FRAMES,
    DEFAULT_LINE_MARGIN,
    DEFAULT_LINE_POSITION,
    DEFAULT_LOGIN_PHOTO_THRESHOLD,
    DEFAULT_LOGIN_REDIRECT_SECONDS,
    DEFAULT_MAX_FACE_WIDTH_RATIO,
    DEFAULT_MAX_HANDS,
    DEFAULT_MIN_DETECTION_CONFIDENCE,
    DEFAULT_MIN_FACE_SHARPNESS,
    DEFAULT_MIN_FACE_WIDTH_RATIO,
    DEFAULT_MIN_GESTURE_CONFIDENCE,
    DEFAULT_MIN_PRESENCE_CONFIDENCE,
    DEFAULT_MIN_TRACKING_CONFIDENCE,
    DEFAULT_PEOPLE_CONFIDENCE,
    DEFAULT_PEOPLE_MODEL_PATH,
    DEFAULT_POINTER_ACTIVE_ZONE_MAX,
    DEFAULT_POINTER_ACTIVE_ZONE_MIN,
    DEFAULT_POINTER_ENABLED,
    DEFAULT_POINTER_MIRROR_X,
    DEFAULT_POINTER_SMOOTHING_ALPHA,
    DEFAULT_POSTURE_CALIBRATION_FRAMES,
    DEFAULT_POSTURE_CONFIRM_FRAMES,
    DEFAULT_POSTURE_KEYPOINT_CONFIDENCE,
    DEFAULT_POSTURE_MAX_HEAD_OFFSET_RATIO,
    DEFAULT_POSTURE_MAX_SHOULDER_TILT_RATIO,
    DEFAULT_POSTURE_MAX_TORSO_ANGLE_DEG,
    DEFAULT_POSTURE_MIN_HEAD_HEIGHT_RATIO,
    DEFAULT_POSTURE_MODEL_PATH,
    DEFAULT_POSTURE_RELEASE_FRAMES,
    DEFAULT_POSTURE_TOLERANCE_HEAD_HEIGHT,
    DEFAULT_POSTURE_TOLERANCE_HEAD_OFFSET,
    DEFAULT_POSTURE_TOLERANCE_SHOULDER_TILT,
    DEFAULT_POSTURE_TOLERANCE_TORSO_ANGLE_DEG,
    DEFAULT_RELEASE_FRAMES,
    DEFAULT_REPEAT_SECONDS,
    DEFAULT_REQUIRE_LOGIN,
    DEFAULT_RULE_DIRECTION_TOLERANCE_DEG,
    DEFAULT_RULE_STRAIGHT_ANGLE_DEG,
    DEFAULT_SCROLL_LINES,
    DEFAULT_SCROLL_REPEAT_SECONDS,
    DEFAULT_SESSION_TIMEOUT_SECONDS,
    DEFAULT_STABILIZATION_FRAMES,
    DEFAULT_TARGET_FPS,
    DEFAULT_THUMB_OPEN_THRESHOLD,
    DEFAULT_TRACK_TIMEOUT_FRAMES,
    FACE_AUTH_MODEL_PATH,
    MAX_ANGLE_DEG,
    MIN_ANGLE_DEG,
    PERSON_LABEL,
    URL_PREFIXES,
)
from recognizer.core.domain.action import MediaKey, ScriptInterpreter
from recognizer.core.domain.app import AppId
from recognizer.core.domain.gesture import (
    GESTURE_NONE,
    GESTURE_POINTING_UP,
    Direction8,
    Finger,
    GestureCatalog,
    RulesPriority,
)
from recognizer.core.domain.hand import Handedness
from recognizer.core.domain.identity import Role
from recognizer.core.domain.pointer import ScrollDirection, SmoothingKind
from recognizer.core.domain.tracking import LineAxis
from recognizer.core.errors import ConfigError


class CameraConfig(BaseModel):
    """Parametros de la camara local."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    device_index: int = Field(default=DEFAULT_CAMERA_DEVICE_INDEX, ge=0)
    width: int = Field(default=DEFAULT_FRAME_WIDTH, gt=0)
    height: int = Field(default=DEFAULT_FRAME_HEIGHT, gt=0)
    target_fps: int = Field(default=DEFAULT_TARGET_FPS, gt=0)


class HandsConfig(BaseModel):
    """Parametros del detector de manos."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_path: str = Field(default=DEFAULT_HAND_MODEL_PATH, min_length=1)
    max_hands: int = Field(default=DEFAULT_MAX_HANDS, ge=1)
    min_detection_confidence: float = Field(default=DEFAULT_MIN_DETECTION_CONFIDENCE, ge=0, le=1)
    min_presence_confidence: float = Field(default=DEFAULT_MIN_PRESENCE_CONFIDENCE, ge=0, le=1)
    min_tracking_confidence: float = Field(default=DEFAULT_MIN_TRACKING_CONFIDENCE, ge=0, le=1)


class RuleThresholdsConfig(BaseModel):
    """Umbrales compartidos por el motor de reglas de gestos."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    straight_angle_deg: float = Field(
        default=DEFAULT_RULE_STRAIGHT_ANGLE_DEG,
        ge=MIN_ANGLE_DEG,
        le=MAX_ANGLE_DEG,
    )
    direction_tolerance_deg: float = Field(
        default=DEFAULT_RULE_DIRECTION_TOLERANCE_DEG,
        ge=MIN_ANGLE_DEG,
        le=MAX_ANGLE_DEG,
    )


class DirectionConditionConfig(BaseModel):
    """Condicion de regla: un dedo apunta en una direccion de ocho sentidos."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finger: Finger
    value: Direction8


class AngleConditionConfig(BaseModel):
    """Condicion de regla: el angulo entre dos dedos cae en un rango."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    a: Finger
    b: Finger
    min_deg: float
    max_deg: float

    @model_validator(mode="after")
    def _validate_range(self) -> Self:
        if not MIN_ANGLE_DEG <= self.min_deg < self.max_deg <= MAX_ANGLE_DEG:
            msg = "El angulo requiere 0 <= min_deg < max_deg <= 180."
            raise ValueError(msg)
        return self


class DistanceConditionConfig(BaseModel):
    """Condicion de regla: las puntas de dos dedos estan mas cerca que un umbral.

    La distancia se normaliza por el tamano de la mano (muneca -> MCP del dedo
    corazon), de modo que ``max_ratio`` es invariante a la distancia a la camara.
    Sirve para gestos de pinza como la senal OK (pulgar e indice).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    a: Finger
    b: Finger
    max_ratio: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _validate_distinct_fingers(self) -> Self:
        if self.a is self.b:
            msg = "La condicion de distancia requiere dos dedos distintos."
            raise ValueError(msg)
        return self


class GestureRuleConfig(BaseModel):
    """Regla declarativa que describe un gesto personalizado."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    extended: tuple[Finger, ...] = ()
    folded: tuple[Finger, ...] = ()
    direction: DirectionConditionConfig | None = None
    angle: AngleConditionConfig | None = None
    distance: DistanceConditionConfig | None = None

    @model_validator(mode="after")
    def _validate_fingers(self) -> Self:
        if set(self.extended) & set(self.folded):
            msg = "Un dedo no puede estar extendido y doblado a la vez."
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_conditions(self) -> Self:
        if (
            not self.extended
            and not self.folded
            and self.direction is None
            and self.angle is None
            and self.distance is None
        ):
            msg = (
                "Una regla requiere al menos una condicion "
                "(extended, folded, direction, angle o distance)."
            )
            raise ValueError(msg)
        return self


class GestureConfig(BaseModel):
    """Parametros del clasificador de gestos y su estabilizador."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_path: str = Field(default=DEFAULT_GESTURE_MODEL_PATH, min_length=1)
    max_hands: int = Field(default=DEFAULT_MAX_HANDS, ge=1)
    min_detection_confidence: float = Field(default=DEFAULT_MIN_DETECTION_CONFIDENCE, ge=0, le=1)
    min_presence_confidence: float = Field(default=DEFAULT_MIN_PRESENCE_CONFIDENCE, ge=0, le=1)
    min_tracking_confidence: float = Field(default=DEFAULT_MIN_TRACKING_CONFIDENCE, ge=0, le=1)
    stabilization_frames: int = Field(default=DEFAULT_STABILIZATION_FRAMES, ge=1)
    release_frames: int = Field(default=DEFAULT_RELEASE_FRAMES, ge=1)
    min_gesture_confidence: float = Field(default=DEFAULT_MIN_GESTURE_CONFIDENCE, ge=0, le=1)
    swap_handedness: bool = False
    custom_labels: tuple[str, ...] = ()
    rules: dict[str, GestureRuleConfig] = Field(default_factory=dict)
    rules_priority: RulesPriority = RulesPriority.RULES_FIRST
    rule_thresholds: RuleThresholdsConfig = Field(default_factory=RuleThresholdsConfig)


class MediaKeyActionConfig(BaseModel):
    """Accion que pulsa una tecla multimedia."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["media_key"] = "media_key"
    key: MediaKey
    repeat_seconds: float = Field(default=DEFAULT_REPEAT_SECONDS, ge=0)


class HotkeyActionConfig(BaseModel):
    """Accion que pulsa una combinacion de teclas."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["hotkey"] = "hotkey"
    keys: tuple[str, ...] = Field(min_length=1)
    repeat_seconds: float = Field(default=DEFAULT_REPEAT_SECONDS, ge=0)


class CommandActionConfig(BaseModel):
    """Accion que lanza un comando local."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["command"] = "command"
    argv: tuple[str, ...] = Field(min_length=1)


class ScriptActionConfig(BaseModel):
    """Accion que ejecuta un script local."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["script"] = "script"
    path: str = Field(min_length=1)
    args: tuple[str, ...] = ()
    interpreter: ScriptInterpreter = ScriptInterpreter.AUTO
    working_dir: str | None = None
    blocking: bool = False
    timeout_seconds: float = Field(default=0.0, ge=0)
    pass_context: bool = False

    @model_validator(mode="after")
    def _require_timeout_when_blocking(self) -> Self:
        if self.blocking and self.timeout_seconds <= 0:
            msg = (
                "Una accion script bloqueante requiere timeout_seconds > 0 "
                "para no detener la camara de forma indefinida."
            )
            raise ValueError(msg)
        return self


class OpenLinksActionConfig(BaseModel):
    """Accion que abre enlaces en el navegador de forma secuencial."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["open_links"] = "open_links"
    urls: tuple[str, ...] = Field(min_length=1)
    browser: str | None = None

    @field_validator("urls")
    @classmethod
    def _validate_urls(cls, urls: tuple[str, ...]) -> tuple[str, ...]:
        for url in urls:
            parsed = urlparse(url)
            if not url.startswith(URL_PREFIXES) or not parsed.netloc:
                msg = f"La URL debe ser http(s) con host valido: {url}"
                raise ValueError(msg)
        return urls


class OpenTabActionConfig(BaseModel):
    """Accion que abre o enfoca una pestana en el navegador controlado."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["open_tab"] = "open_tab"
    tab: str = Field(min_length=1)
    urls: tuple[str, ...] = ()

    @field_validator("urls")
    @classmethod
    def _validate_urls(cls, urls: tuple[str, ...]) -> tuple[str, ...]:
        for url in urls:
            parsed = urlparse(url)
            if not url.startswith(URL_PREFIXES) or not parsed.netloc:
                msg = f"La URL debe ser http(s) con host valido: {url}"
                raise ValueError(msg)
        return urls


class TabSeekActionConfig(BaseModel):
    """Accion que posiciona el video de una pestana."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["tab_seek"] = "tab_seek"
    tab: str = Field(min_length=1)
    fraction: float = Field(ge=0.0, le=1.0)


class TabPressActionConfig(BaseModel):
    """Accion que envia teclas a una pestana."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["tab_press"] = "tab_press"
    tab: str = Field(min_length=1)
    keys: tuple[str, ...] = Field(min_length=1)


class ScrollActionConfig(BaseModel):
    """Accion que desplaza la rueda del raton ante un gesto sostenido."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["scroll"] = "scroll"
    direction: ScrollDirection
    lines: int = Field(default=DEFAULT_SCROLL_LINES, ge=1)
    repeat_seconds: float = Field(default=DEFAULT_SCROLL_REPEAT_SECONDS, ge=0)
    cooldown_seconds: float | None = Field(default=None, ge=0)


ActionConfig = Annotated[
    MediaKeyActionConfig
    | HotkeyActionConfig
    | CommandActionConfig
    | ScriptActionConfig
    | OpenLinksActionConfig
    | OpenTabActionConfig
    | TabSeekActionConfig
    | TabPressActionConfig
    | ScrollActionConfig,
    Field(discriminator="type"),
]


class MenuConfig(BaseModel):
    """Menu compuesto: una mano sostiene el modificador y la otra elige."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    hand: Handedness
    modifier: str = Field(min_length=1)
    consume_trigger: bool = True
    options: dict[str, ActionConfig] = Field(min_length=1)


class ActionsConfig(BaseModel):
    """Acciones locales y su mapeo por gesto confirmado."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cooldown_seconds: float = Field(default=DEFAULT_ACTION_COOLDOWN_SECONDS, ge=0)
    mappings: dict[str, ActionConfig] = Field(default_factory=dict)
    menus: dict[str, MenuConfig] = Field(default_factory=dict)

    @field_validator("mappings")
    @classmethod
    def _reject_none_gesture(
        cls,
        mappings: dict[str, ActionConfig],
    ) -> dict[str, ActionConfig]:
        if GESTURE_NONE.value in mappings:
            msg = "El gesto None no puede mapearse a una accion."
            raise ValueError(msg)
        return mappings


class BrowserTabConfig(BaseModel):
    """Pestana registrada en el navegador controlado."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str
    match: str = ""

    @model_validator(mode="after")
    def _default_match(self) -> Self:
        if not self.match:
            parsed = urlparse(self.url)
            object.__setattr__(self, "match", parsed.netloc)
        return self

    @field_validator("url")
    @classmethod
    def _validate_url(cls, url: str) -> str:
        parsed = urlparse(url)
        if not url.startswith(URL_PREFIXES) or not parsed.netloc:
            msg = f"La URL debe ser http(s) con host valido: {url}"
            raise ValueError(msg)
        return url


class BrowserConfig(BaseModel):
    """Navegador controlado: instancia Chromium aislada para acciones."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    executable: str | None = None
    debugging_port: int = Field(default=DEFAULT_BROWSER_DEBUGGING_PORT, gt=0, le=65535)
    user_data_dir: str | None = None
    tabs: dict[str, BrowserTabConfig] = Field(default_factory=dict)


class ActiveZoneConfig(BaseModel):
    """Zona activa del fotograma que se proyecta sobre toda la pantalla."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    x_min: float = Field(default=DEFAULT_POINTER_ACTIVE_ZONE_MIN, ge=0, le=1)
    x_max: float = Field(default=DEFAULT_POINTER_ACTIVE_ZONE_MAX, ge=0, le=1)
    y_min: float = Field(default=DEFAULT_POINTER_ACTIVE_ZONE_MIN, ge=0, le=1)
    y_max: float = Field(default=DEFAULT_POINTER_ACTIVE_ZONE_MAX, ge=0, le=1)

    @model_validator(mode="after")
    def _validate_ranges(self) -> Self:
        if self.x_min >= self.x_max:
            msg = "La zona activa requiere x_min < x_max."
            raise ValueError(msg)
        if self.y_min >= self.y_max:
            msg = "La zona activa requiere y_min < y_max."
            raise ValueError(msg)
        return self


class PointerConfig(BaseModel):
    """Puntero virtual: activacion, calibracion y suavizado."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = DEFAULT_POINTER_ENABLED
    activation_gesture: str = GESTURE_POINTING_UP.value
    mirror_x: bool = DEFAULT_POINTER_MIRROR_X
    smoothing: SmoothingKind = SmoothingKind.EMA
    alpha: float = Field(default=DEFAULT_POINTER_SMOOTHING_ALPHA, gt=0, le=1)
    active_zone: ActiveZoneConfig = Field(default_factory=ActiveZoneConfig)
    thumb_open_threshold: float = Field(default=DEFAULT_THUMB_OPEN_THRESHOLD, gt=0, le=2)

    @field_validator("activation_gesture")
    @classmethod
    def _reject_none_gesture(cls, gesture: str) -> str:
        if gesture == GESTURE_NONE.value:
            msg = "El gesto None no puede activar el puntero."
            raise ValueError(msg)
        return gesture


class CountingLineConfig(BaseModel):
    """Linea de conteo del contador de personas (entradas/salidas)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = True
    axis: LineAxis = LineAxis.VERTICAL
    position: float = Field(default=DEFAULT_LINE_POSITION, gt=0, lt=1)
    margin: float = Field(default=DEFAULT_LINE_MARGIN, ge=0, lt=0.5)
    invert: bool = False
    confirm_frames: int = Field(default=DEFAULT_LINE_CONFIRM_FRAMES, ge=1)
    track_timeout_frames: int = Field(default=DEFAULT_TRACK_TIMEOUT_FRAMES, ge=1)

    @model_validator(mode="after")
    def _validate_margin(self) -> Self:
        if self.margin >= min(self.position, 1 - self.position):
            msg = "La linea requiere margin < min(position, 1-position)."
            raise ValueError(msg)
        return self


class PeopleCounterConfig(BaseModel):
    """Contador de personas: modelo YOLO, umbrales y linea de conteo."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_path: str = Field(default=DEFAULT_PEOPLE_MODEL_PATH, min_length=1)
    min_confidence: float = Field(default=DEFAULT_PEOPLE_CONFIDENCE, ge=0, le=1)
    target_label: str = Field(default=PERSON_LABEL, min_length=1)
    line: CountingLineConfig = Field(default_factory=CountingLineConfig)


class IntrusionZoneConfig(BaseModel):
    """Zona de intrusion del anti-intrusos: rectangulo normalizado 0..1."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = True
    x_min: float = Field(default=DEFAULT_INTRUSION_ZONE_X_MIN, ge=0, le=1)
    y_min: float = Field(default=DEFAULT_INTRUSION_ZONE_Y_MIN, ge=0, le=1)
    x_max: float = Field(default=DEFAULT_INTRUSION_ZONE_X_MAX, ge=0, le=1)
    y_max: float = Field(default=DEFAULT_INTRUSION_ZONE_Y_MAX, ge=0, le=1)
    confirm_frames: int = Field(default=DEFAULT_INTRUSION_CONFIRM_FRAMES, ge=1)
    release_frames: int = Field(default=DEFAULT_INTRUSION_RELEASE_FRAMES, ge=1)

    @model_validator(mode="after")
    def _validate_rectangle(self) -> Self:
        if self.x_min >= self.x_max:
            msg = "La zona de intrusion requiere x_min < x_max."
            raise ValueError(msg)
        if self.y_min >= self.y_max:
            msg = "La zona de intrusion requiere y_min < y_max."
            raise ValueError(msg)
        return self


class IntrusionAlertConfig(BaseModel):
    """Alerta sonora del anti-intrusos: activacion y repeticion mientras dura."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = True
    repeat_seconds: float = Field(default=DEFAULT_INTRUSION_ALERT_REPEAT_SECONDS, ge=0)


class AntiIntruderConfig(BaseModel):
    """Anti-intrusos: modelo YOLO, umbrales, zona de intrusion y alerta."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_path: str = Field(default=DEFAULT_PEOPLE_MODEL_PATH, min_length=1)
    min_confidence: float = Field(default=DEFAULT_PEOPLE_CONFIDENCE, ge=0, le=1)
    target_label: str = Field(default=PERSON_LABEL, min_length=1)
    zone: IntrusionZoneConfig = Field(default_factory=IntrusionZoneConfig)
    alert: IntrusionAlertConfig = Field(default_factory=IntrusionAlertConfig)


class PostureAlertConfig(BaseModel):
    """Alerta sonora de postura: activacion y repeticion mientras dura."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = True
    repeat_seconds: float = Field(default=DEFAULT_INTRUSION_ALERT_REPEAT_SECONDS, ge=0)


class PostureTolerancesConfig(BaseModel):
    """Desvio admitido respecto a la linea base calibrada."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    head_offset: float = Field(default=DEFAULT_POSTURE_TOLERANCE_HEAD_OFFSET, ge=0)
    head_height: float = Field(default=DEFAULT_POSTURE_TOLERANCE_HEAD_HEIGHT, ge=0)
    torso_angle_deg: float = Field(
        default=DEFAULT_POSTURE_TOLERANCE_TORSO_ANGLE_DEG, ge=0, le=MAX_ANGLE_DEG
    )
    shoulder_tilt: float = Field(default=DEFAULT_POSTURE_TOLERANCE_SHOULDER_TILT, ge=0)


class PostureConfig(BaseModel):
    """Postura ergonomica: modelo YOLO pose, calibracion, umbrales y debounce.

    Con ``calibration_frames > 0`` la app aprende la postura correcta al inicio
    (el usuario se sienta derecho unos segundos) y luego avisa de los desvios
    respecto a esa linea base usando ``tolerances``. Con ``calibration_frames: 0``
    se usan los umbrales absolutos. Las metricas se normalizan por una escala
    corporal (ancho de hombros o largo del torso en perfil).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_path: str = Field(default=DEFAULT_POSTURE_MODEL_PATH, min_length=1)
    min_confidence: float = Field(default=DEFAULT_PEOPLE_CONFIDENCE, ge=0, le=1)
    min_keypoint_confidence: float = Field(default=DEFAULT_POSTURE_KEYPOINT_CONFIDENCE, ge=0, le=1)
    calibration_frames: int = Field(default=DEFAULT_POSTURE_CALIBRATION_FRAMES, ge=0)
    tolerances: PostureTolerancesConfig = Field(default_factory=PostureTolerancesConfig)
    max_head_offset_ratio: float = Field(default=DEFAULT_POSTURE_MAX_HEAD_OFFSET_RATIO, gt=0)
    min_head_height_ratio: float = Field(default=DEFAULT_POSTURE_MIN_HEAD_HEIGHT_RATIO, ge=0)
    max_torso_angle_deg: float = Field(
        default=DEFAULT_POSTURE_MAX_TORSO_ANGLE_DEG, ge=MIN_ANGLE_DEG, le=MAX_ANGLE_DEG
    )
    max_shoulder_tilt_ratio: float = Field(default=DEFAULT_POSTURE_MAX_SHOULDER_TILT_RATIO, gt=0)
    confirm_frames: int = Field(default=DEFAULT_POSTURE_CONFIRM_FRAMES, ge=1)
    release_frames: int = Field(default=DEFAULT_POSTURE_RELEASE_FRAMES, ge=1)
    alert: PostureAlertConfig = Field(default_factory=PostureAlertConfig)


class FaceAuthConfig(BaseModel):
    """Reconocimiento facial: modelo InsightFace, captura, matching y almacen.

    ``min_confidence`` filtra detecciones debiles; ``min_face_width_ratio`` y
    ``max_face_width_ratio`` guian la distancia; ``min_sharpness`` exige
    quietud; ``enrollment_samples`` fija las muestras del enrolamiento;
    ``match_threshold`` es la distancia coseno maxima aceptada.
    ``default_role`` es el rol de los nuevos enrolados (el primero es admin);
    ``session_timeout_seconds`` es la vigencia de la sesion tras el login
    (0 = sin expiracion); ``require_login`` filtra el menu por rol (false =
    modo abierto, sin sesion todo permitido); ``permissions`` es un override
    por app (``{app_id: [roles]}``) sobre la matriz por defecto.
    ``access_dir`` guarda el registro de accesos (logins.jsonl + fotos);
    ``login_photo_threshold`` es la distancia coseno maxima para elegir la foto
    del login: mas estricta que ``match_threshold`` (menor distancia = mejor),
    de modo que solo se guarda una imagen cuando la coincidencia es clara.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_path: str = Field(default=FACE_AUTH_MODEL_PATH, min_length=1)
    min_confidence: float = Field(default=DEFAULT_FACE_CONFIDENCE, ge=0, le=1)
    det_size: int = Field(default=DEFAULT_FACE_DET_SIZE, ge=128, le=1280)
    process_every_n_frames: int = Field(default=DEFAULT_FACE_PROCESS_EVERY_N_FRAMES, ge=1)
    max_inference_fps: float = Field(default=DEFAULT_FACE_MAX_INFERENCE_FPS, ge=0)
    min_face_width_ratio: float = Field(default=DEFAULT_MIN_FACE_WIDTH_RATIO, ge=0, le=1)
    max_face_width_ratio: float = Field(default=DEFAULT_MAX_FACE_WIDTH_RATIO, ge=0, le=1)
    min_sharpness: float = Field(default=DEFAULT_MIN_FACE_SHARPNESS, ge=0)
    enrollment_samples: int = Field(default=DEFAULT_ENROLLMENT_SAMPLES, ge=1)
    match_threshold: float = Field(default=DEFAULT_FACE_MATCH_THRESHOLD, ge=0)
    login_photo_threshold: float = Field(default=DEFAULT_LOGIN_PHOTO_THRESHOLD, ge=0)
    login_redirect_seconds: int = Field(default=DEFAULT_LOGIN_REDIRECT_SECONDS, ge=0)
    confirm_frames: int = Field(default=DEFAULT_FACE_CONFIRM_FRAMES, ge=1)
    release_frames: int = Field(default=DEFAULT_FACE_RELEASE_FRAMES, ge=1)
    store_dir: str = Field(default=DEFAULT_FACE_STORE_DIR, min_length=1)
    access_dir: str = Field(default=DEFAULT_ACCESS_DIR, min_length=1)
    default_role: Role = Role(DEFAULT_FACE_DEFAULT_ROLE)
    session_timeout_seconds: int = Field(default=DEFAULT_SESSION_TIMEOUT_SECONDS, ge=0)
    require_login: bool = DEFAULT_REQUIRE_LOGIN
    permissions: dict[str, list[Role]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_widths(self) -> Self:
        if self.min_face_width_ratio >= self.max_face_width_ratio:
            msg = "La captura facial requiere min_face_width_ratio < max_face_width_ratio."
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_login_photo_threshold(self) -> Self:
        if self.login_photo_threshold > self.match_threshold:
            msg = (
                "login_photo_threshold debe ser <= match_threshold (una distancia "
                "coseno menor es una coincidencia mejor)."
            )
            raise ValueError(msg)
        return self

    @field_validator("permissions")
    @classmethod
    def _validate_permission_apps(cls, permissions: dict[str, list[Role]]) -> dict[str, list[Role]]:
        known = {app.value for app in AppId}
        for key in permissions:
            if key not in known:
                msg = f"Permiso para aplicacion desconocida: {key}"
                raise ValueError(msg)
        return permissions


class AppsConfig(BaseModel):
    """Habilitacion de apps del launcher (override sobre el catalogo).
    Solo afecta a apps implementadas: las que aun no existen se muestran como
    "proximamente" independientemente de este valor.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: dict[AppId, bool] = Field(default_factory=dict)

    def is_enabled(self, app_id: AppId) -> bool:
        """Indica si la app esta habilitada; por defecto, si."""
        return self.enabled.get(app_id, True)


class AppConfig(BaseModel):
    """Configuracion raiz de la aplicacion."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    camera: CameraConfig = Field(default_factory=CameraConfig)
    hands: HandsConfig = Field(default_factory=HandsConfig)
    gestures: GestureConfig = Field(default_factory=GestureConfig)
    pointer: PointerConfig = Field(default_factory=PointerConfig)
    actions: ActionsConfig = Field(default_factory=ActionsConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    people_counter: PeopleCounterConfig = Field(default_factory=PeopleCounterConfig)
    anti_intruder: AntiIntruderConfig = Field(default_factory=AntiIntruderConfig)
    posture: PostureConfig = Field(default_factory=PostureConfig)
    face_auth: FaceAuthConfig = Field(default_factory=FaceAuthConfig)
    apps: AppsConfig = Field(default_factory=AppsConfig)

    def gesture_catalog(self) -> GestureCatalog:
        """Reconstruye el catalogo de gestos declarado por la configuracion."""
        return GestureCatalog.from_labels(
            custom_labels=self.gestures.custom_labels,
            rule_names=tuple(self.gestures.rules),
        )

    @model_validator(mode="after")
    def _validate_gesture_references(self) -> Self:
        try:
            catalog = self.gesture_catalog()
            for label in self.actions.mappings:
                catalog.require(label)
            for menu in self.actions.menus.values():
                catalog.require(menu.modifier)
                for label in menu.options:
                    catalog.require(label)
            catalog.require(self.pointer.activation_gesture)
        except ConfigError as exc:
            raise ValueError(str(exc)) from exc
        return self

    @model_validator(mode="after")
    def _validate_browser_tab_references(self) -> Self:
        tab_names = set(self.browser.tabs)
        for label, spec in self.actions.mappings.items():
            tab_ref = getattr(spec, "tab", None)
            if tab_ref is not None and tab_ref not in tab_names:
                msg = (
                    f"La accion '{label}' referencia la pestana '{tab_ref}' "
                    f"que no esta definida en browser.tabs."
                )
                raise ValueError(msg)
        for menu_name, menu_config in self.actions.menus.items():
            for opt_label, spec in menu_config.options.items():
                tab_ref = getattr(spec, "tab", None)
                if tab_ref is not None and tab_ref not in tab_names:
                    msg = (
                        f"La opcion '{opt_label}' del menu '{menu_name}' "
                        f"referencia la pestana '{tab_ref}' que no esta en browser.tabs."
                    )
                    raise ValueError(msg)
        return self
