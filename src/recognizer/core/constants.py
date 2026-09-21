"""Constantes compartidas del nucleo.

Aqui viven los valores por defecto y limites usados en mas de un modulo.
Los valores configurables por el usuario pertenecen a config.yaml.
"""

DEFAULT_CAMERA_DEVICE_INDEX = 0
DEFAULT_CAMERA_ENUMERATOR_MAX_INDEX = 8
DEFAULT_FRAME_WIDTH = 640
DEFAULT_FRAME_HEIGHT = 480
DEFAULT_TARGET_FPS = 30
# Búfer de captura mínimo: evita acumular fotogramas viejos cuando la
# inferencia es más lenta que la cámara (retraso creciente en cámaras de red o
# del teléfono). 1 = procesar siempre el fotograma más reciente.
DEFAULT_CAPTURE_BUFFER_SIZE = 1
# Captura asíncrona (`LatestFrameSource`): un hilo drena la cámara y el bucle
# de dibujo espera al siguiente fotograma nuevo. Evita que la inferencia lenta
# (facial) frene la lectura y sature el stream de red.
LATEST_FRAME_READ_TIMEOUT_SECONDS = 1.0
LATEST_FRAME_JOIN_TIMEOUT_SECONDS = 2.0
LATEST_FRAME_FAILURE_SLEEP_SECONDS = 0.01
# Worker de inferencia facial: espera a un fotograma nuevo y se detiene limpio.
FACE_WORKER_WAIT_TIMEOUT_SECONDS = 0.2
FACE_WORKER_JOIN_TIMEOUT_SECONDS = 2.0

DEFAULT_HAND_MODEL_PATH = "models/hand_landmarker.task"
DEFAULT_MAX_HANDS = 2
DEFAULT_MIN_DETECTION_CONFIDENCE = 0.5
DEFAULT_MIN_PRESENCE_CONFIDENCE = 0.5
DEFAULT_MIN_TRACKING_CONFIDENCE = 0.5

DEFAULT_GESTURE_MODEL_PATH = "models/gesture_recognizer.task"
DEFAULT_STABILIZATION_FRAMES = 5
DEFAULT_RELEASE_FRAMES = 5
DEFAULT_MIN_GESTURE_CONFIDENCE = 0.5

ACTION_LOGGER_NAME = "recognizer.actions"
DEFAULT_ACTION_COOLDOWN_SECONDS = 1.0
DEFAULT_REPEAT_SECONDS = 0.0  # 0 = sin repeticion

CONTEXT_ENV_GESTURE = "RECOGNIZER_GESTURE"
CONTEXT_ENV_HANDEDNESS = "RECOGNIZER_HANDEDNESS"
CONTEXT_ENV_CONFIDENCE = "RECOGNIZER_CONFIDENCE"
CONTEXT_ENV_TIMESTAMP = "RECOGNIZER_TIMESTAMP"

HTTP_URL_PREFIX = "http://"
HTTPS_URL_PREFIX = "https://"
URL_PREFIXES = (HTTP_URL_PREFIX, HTTPS_URL_PREFIX)

POINTER_LOGGER_NAME = "recognizer.pointer"
POINTER_MAX_VISIBLE_HANDS = 1
DEFAULT_POINTER_ENABLED = True
DEFAULT_POINTER_ACTIVE_ZONE_MIN = 0.2
DEFAULT_POINTER_ACTIVE_ZONE_MAX = 0.8
DEFAULT_POINTER_MIRROR_X = True
DEFAULT_POINTER_SMOOTHING_ALPHA = 0.35
DEFAULT_THUMB_OPEN_THRESHOLD = 0.5

DEFAULT_SCROLL_LINES = 3
DEFAULT_SCROLL_REPEAT_SECONDS = 0.15
MIN_SCROLL_LINES = 1
SCROLL_FIXED_AXIS = 0

MIN_ANGLE_DEG = 0.0
MAX_ANGLE_DEG = 180.0
DEFAULT_RULE_STRAIGHT_ANGLE_DEG = 160.0
DEFAULT_RULE_DIRECTION_TOLERANCE_DEG = 30.0
RULE_CONFIDENCE = 1.0
MIN_VECTOR_NORM = 1e-9

MILLISECONDS_PER_SECOND = 1000
MIN_ELAPSED_SECONDS = 1e-9
MAX_CONSECUTIVE_READ_FAILURES = 30
FPS_LOG_INTERVAL = 30
ESC_KEY = 27
WINDOW_TOPMOST_ENABLED = 1
WINDOW_TOPMOST_DISABLED = 0
WINDOW_MIN_VISIBLE_VALUE = 1.0

PERSON_LABEL = "person"
DEFAULT_PEOPLE_MODEL_PATH = "models/yolo26n.pt"
DEFAULT_PEOPLE_CONFIDENCE = 0.5

DEFAULT_LINE_POSITION = 0.5
DEFAULT_LINE_CONFIRM_FRAMES = 2
DEFAULT_LINE_MARGIN = 0.05
DEFAULT_TRACK_TIMEOUT_FRAMES = 30
DEFAULT_TRACKER_CONFIG = "bytetrack.yaml"

DEFAULT_INTRUSION_ZONE_X_MIN = 0.25
DEFAULT_INTRUSION_ZONE_Y_MIN = 0.4
DEFAULT_INTRUSION_ZONE_X_MAX = 0.75
DEFAULT_INTRUSION_ZONE_Y_MAX = 0.9
DEFAULT_INTRUSION_CONFIRM_FRAMES = 3
DEFAULT_INTRUSION_RELEASE_FRAMES = 5
DEFAULT_INTRUSION_ALERT_REPEAT_SECONDS = 2.0

DEFAULT_POSTURE_MODEL_PATH = "models/yolo26n-pose.pt"
DEFAULT_POSTURE_KEYPOINT_CONFIDENCE = 0.5
DEFAULT_POSTURE_MAX_HEAD_OFFSET_RATIO = 0.35
DEFAULT_POSTURE_MIN_HEAD_HEIGHT_RATIO = 0.7
DEFAULT_POSTURE_MAX_TORSO_ANGLE_DEG = 15.0
DEFAULT_POSTURE_MAX_SHOULDER_TILT_RATIO = 0.15
DEFAULT_POSTURE_CONFIRM_FRAMES = 5
DEFAULT_POSTURE_RELEASE_FRAMES = 10
# Calibracion: fotogramas que se promedian para aprender la postura correcta.
DEFAULT_POSTURE_CALIBRATION_FRAMES = 60
# Tolerancias de desvio respecto a la linea base calibrada.
DEFAULT_POSTURE_TOLERANCE_HEAD_OFFSET = 0.15
DEFAULT_POSTURE_TOLERANCE_HEAD_HEIGHT = 0.2
DEFAULT_POSTURE_TOLERANCE_TORSO_ANGLE_DEG = 8.0
DEFAULT_POSTURE_TOLERANCE_SHOULDER_TILT = 0.1
# Si el ancho de hombros cae por debajo de esta fraccion del torso (vista de
# perfil) se usa el largo del torso como escala en vez del ancho de hombros.
POSTURE_PROFILE_SHOULDER_RATIO = 0.5

# Asistencia / manos arriba (etapa 16): brazos levantados con YOLO pose.
# Un brazo cuenta cuando su muneca queda por encima del hombro al menos
# `raise_margin` (coordenadas normalizadas 0..1, eje Y hacia abajo).
DEFAULT_ASSISTANCE_MODEL_PATH = "models/yolo26n-pose.pt"
DEFAULT_ASSISTANCE_KEYPOINT_CONFIDENCE = 0.5
DEFAULT_ASSISTANCE_RAISE_MARGIN = 0.05
DEFAULT_ASSISTANCE_REQUIRED_ARMS = 2
MIN_RAISED_ARMS = 1
MAX_RAISED_ARMS = 2
DEFAULT_ASSISTANCE_CONFIRM_FRAMES = 5
DEFAULT_ASSISTANCE_RELEASE_FRAMES = 10

# Loitering / zona permanencia (etapa 17a): dwell time por track en zona.
DEFAULT_LOITERING_DWELL_THRESHOLD_SECONDS = 10.0
DEFAULT_LOITERING_CONFIRM_FRAMES = 3
DEFAULT_LOITERING_RELEASE_FRAMES = 5
DEFAULT_LOITERING_ALERT_REPEAT_SECONDS = 2.0

# Vacancy / zona vacia (etapa 17b): alerta cuando no hay nadie en camara.
DEFAULT_VACANCY_ABSENCE_THRESHOLD_SECONDS = 5.0
DEFAULT_VACANCY_CONFIRM_FRAMES = 3
DEFAULT_VACANCY_RELEASE_FRAMES = 5
DEFAULT_VACANCY_ALERT_REPEAT_SECONDS = 2.0

# Vehicle counter / conteo de autos (etapa 18): tracking YOLO + cruces de linea.
VEHICLE_LABEL = "car"
DEFAULT_VEHICLE_MODEL_PATH = "models/yolo26n.pt"
DEFAULT_VEHICLE_CONFIDENCE = 0.5

# Privacy blur / desenfoque de rostros (etapa 19): deteccion + blur en vivo.
DEFAULT_PRIVACY_MODEL_PATH = "models/yolo26n.pt"
DEFAULT_PRIVACY_CONFIDENCE = 0.5
DEFAULT_PRIVACY_TARGET_LABELS = ("face", "car", "license plate")
DEFAULT_PRIVACY_BLUR_STRENGTH = 51
MIN_BLUR_STRENGTH = 3
MAX_BLUR_STRENGTH = 99

DEFAULT_BROWSER_DEBUGGING_PORT: int = 9222
DEFAULT_CDP_CONNECT_TIMEOUT: float = 2.0
DEFAULT_CDP_COMMAND_TIMEOUT: float = 3.0
CDP_CHROME_LAUNCH_TIMEOUT: float = 5.0
CDP_POLL_INTERVAL: float = 0.5

FACE_AUTH_MODEL_PATH = "models/buffalo_s"
DEFAULT_FACE_CONFIDENCE = 0.5
DEFAULT_MIN_FACE_WIDTH_RATIO = 0.18
DEFAULT_MAX_FACE_WIDTH_RATIO = 0.55
DEFAULT_MIN_FACE_SHARPNESS = 80.0
DEFAULT_ENROLLMENT_SAMPLES = 5
DEFAULT_FACE_MATCH_THRESHOLD = 0.45
DEFAULT_FACE_CONFIRM_FRAMES = 3
DEFAULT_FACE_RELEASE_FRAMES = 5
DEFAULT_FACE_STORE_DIR = "data/faces"
# Foto de enrolamiento (<id>.png) junto al JSON de cada rostro.
FACE_PREVIEW_SUFFIX = ".png"
# Registro de accesos (logins): JSONL + imagenes de cada login.
DEFAULT_ACCESS_DIR = "data/access"
ACCESS_LOG_FILENAME = "logins.jsonl"
ACCESS_IMAGES_DIRNAME = "images"
# Distancia coseno maxima para elegir la foto del login: mas estricta que
# match_threshold (menor distancia = mejor), para guardar una foto nitida.
DEFAULT_LOGIN_PHOTO_THRESHOLD = 0.35
DEFAULT_FACE_DET_SIZE = 640
# Cada cuantos fotogramas se ejecuta la inferencia facial. 1 = todos. Subirlo
# alivia CPUs lentas o camaras de red: la vista sigue fluida y la deteccion se
# repite cada N fotogramas reutilizando el ultimo resultado.
DEFAULT_FACE_PROCESS_EVERY_N_FRAMES = 1
# Tope de inferencias por segundo (0 = sin tope). Acota la CPU: con rostro en
# camara la inferencia es mas cara y, sin tope, satura el equipo y traba el
# stream/dibujo. 5 FPS alcanza para login y enrolamiento.
DEFAULT_FACE_MAX_INFERENCE_FPS = 5.0
# Segundos de cuenta regresiva tras un login correcto antes de volver al menu
# (0 = no redirige solo; hay que salir con ESC/q).
DEFAULT_LOGIN_REDIRECT_SECONDS = 3
DEFAULT_FACE_CENTER_TOLERANCE = 0.15
FACE_ID_PREFIX = "F-"
FACE_ID_WIDTH = 4
# Alfabeto del sufijo del ID facial: sin 0/O/1/I/L para no confundir al
# tipearlo en el login con clave. Los IDs son aleatorios (no secuenciales)
# para que no delaten orden ni quien es admin.
FACE_ID_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
MAX_FACE_ID_ATTEMPTS = 100
FACE_MAX_COSINE_DISTANCE = 2.0
DEFAULT_FACE_DEFAULT_ROLE = "operator"
# Clave de respaldo por usuario (login sin camara): hash PBKDF2-HMAC-SHA256 con
# sal aleatoria. La clave se pide en el enrolamiento con confirmacion.
PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 600_000
PASSWORD_SALT_BYTES = 16
DEFAULT_MIN_PASSWORD_LENGTH = 4
# DNI argentino: 7 u 8 digitos (se aceptan puntos y espacios al ingresarlo).
NATIONAL_ID_MIN_DIGITS = 7
NATIONAL_ID_MAX_DIGITS = 8
# Prompts estables del enrolamiento y del login con clave; la GUI los usa como
# claves del lector en cola (no dependen de face_auth para no cargar modelos).
FACE_ENROLL_NAME_PROMPT = "Nombre para enrolar: "
FACE_ENROLL_ROLE_PROMPT = "Rol (admin/operator/viewer) [operator]: "
FACE_ENROLL_NATIONAL_ID_PROMPT = "DNI (7 u 8 digitos): "
FACE_ENROLL_PASSWORD_PROMPT = "Clave para el usuario: "
FACE_ENROLL_PASSWORD_CONFIRM_PROMPT = "Confirma la clave: "
FACE_LOGIN_USER_PROMPT = "Usuario (ID o DNI): "
FACE_LOGIN_PASSWORD_PROMPT = "Clave: "
DEFAULT_SESSION_TIMEOUT_SECONDS = 8 * 3600
SESSION_FILENAME = "session.json"
ANONYMOUS_FACE_ID = "anonimo"
ANONYMOUS_NAME = "invitado"
DEFAULT_REQUIRE_LOGIN = False
LOCAL_IDENTITY_FACE_ID = "local"
LOCAL_IDENTITY_NAME = "local"
