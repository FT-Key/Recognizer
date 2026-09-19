"""App Reconocimiento facial: enrolamiento y login con InsightFace.

Una sola via de inferencia (InsightFace buffalo en CPU), pero **desacoplada del
dibujo**: un hilo drena la camara (`LatestFrameSource`) y un worker reconoce el
fotograma mas reciente mientras el bucle principal dibuja a ritmo de camara.
Asi la inferencia lenta no frena la lectura ni satura el stream de red (camara
del telefono). Al salir (ESC/q) devuelve el control al launcher.
"""

import logging
import threading
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass

import cv2

from recognizer.adapters.alert_sound import SilentAlert
from recognizer.adapters.camera_opencv import OpenCVCamera
from recognizer.adapters.file_face_repository import FileFaceRepository
from recognizer.adapters.file_identity_provider import FileIdentityProvider
from recognizer.adapters.insightface_recognizer import InsightFaceRecognizer
from recognizer.adapters.latest_frame_source import LatestFrameSource
from recognizer.adapters.overlay_face import draw_face_overlay
from recognizer.bootstrap import resolve_camera_config
from recognizer.cli.console import log_step
from recognizer.cli.paths import prepare_workspace
from recognizer.cli.runtime import RuntimeCallbacks, run_camera_loop
from recognizer.core.config import FaceAuthConfig
from recognizer.core.constants import (
    FACE_MAX_COSINE_DISTANCE,
    FACE_WORKER_JOIN_TIMEOUT_SECONDS,
    FACE_WORKER_WAIT_TIMEOUT_SECONDS,
)
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.domain.face import (
    CaptureGuidance,
    EnrolledFace,
    EnrollmentBuilder,
    FaceBox,
    FaceMatch,
    FaceMatcher,
    FaceObservation,
    LoginDebouncer,
    assess_capture,
)
from recognizer.core.domain.identity import Identity, Role
from recognizer.core.errors import FaceRecognizerError, RecognizerError
from recognizer.core.pipeline.builder import PipelineBuilder
from recognizer.core.pipeline.context import FrameContext
from recognizer.settings import load_config

LOGGER = logging.getLogger("recognizer.face_auth")

ENROLL_WINDOW_NAME = "Enrolamiento facial"
LOGIN_WINDOW_NAME = "Login facial"
AUTH_MENU_TEXT = "1) Enrolar rostro  2) Login facial  3) Cerrar sesion  0) Volver"
AUTH_PROMPT = "Elige (1/2/3/0): "
NAME_PROMPT = "Nombre para enrolar: "
ROLE_PROMPT = "Rol (admin/operator/viewer) [operator]: "
NO_FACE_DISTANCE = FACE_MAX_COSINE_DISTANCE
UNKNOWN_TEXT = "Desconocido"
RECOGNIZING_TEXT = "Reconociendo..."


@dataclass
class _EnrollState:
    """Estado mutable del enrolamiento compartido por los callbacks."""

    guidance: CaptureGuidance | None = None
    boxes: tuple[FaceBox, ...] = ()
    accepted: int = 0
    required: int = 0
    saved: bool = False


@dataclass
class _LoginState:
    """Estado mutable del login compartido por los callbacks."""

    guidance: CaptureGuidance | None = None
    boxes: tuple[FaceBox, ...] = ()
    login_text: str = ""
    highlight_ok: bool = False
    greeted_id: str | None = None


class _RecognitionWorker:
    """Hilo que reconoce el fotograma mas reciente sin frenar la captura.

    Toma fotogramas de ``LatestFrameSource`` sin consumirlos (version propia),
    reconoce en el hilo worker y entrega las observaciones a ``process``. El
    bucle principal solo dibuja, asi que la vista va a ritmo de camara aunque
    la inferencia tarde cientos de milisegundos.
    """

    def __init__(
        self,
        *,
        source: LatestFrameSource,
        recognizer: InsightFaceRecognizer,
        process: Callable[[tuple[FaceObservation, ...]], None],
        process_every_n_frames: int,
        logger: logging.Logger,
    ) -> None:
        self._source = source
        self._recognizer = recognizer
        self._process = process
        self._every = max(1, process_every_n_frames)
        self._logger = logger
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._error: RecognizerError | None = None

    def start(self) -> None:
        """Arranca el hilo de inferencia."""
        self._thread = threading.Thread(target=self._run, name="recognizer-face-infer", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        version = 0
        seen = 0
        while not self._stop.is_set():
            got = self._source.wait_for_new(version, timeout=FACE_WORKER_WAIT_TIMEOUT_SECONDS)
            if got is None:
                continue
            frame, version = got
            seen += 1
            if seen % self._every != 0:
                continue
            try:
                observations = self._recognizer.recognize(frame)
            except Exception as exc:  # el hilo no debe morir en silencio
                error = (
                    exc
                    if isinstance(exc, RecognizerError)
                    else FaceRecognizerError(f"Fallo la inferencia facial: {exc}")
                )
                self._error = error
                self._logger.error("Fallo la inferencia facial: %s", exc)
                self._stop.set()
                return
            if self._stop.is_set():
                return
            self._process(observations)

    def stop(self) -> None:
        """Detiene el hilo y espera a que termine."""
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=FACE_WORKER_JOIN_TIMEOUT_SECONDS)
            if thread.is_alive():
                self._logger.warning(
                    "El worker facial no termino en %.1fs; se continua el cierre.",
                    FACE_WORKER_JOIN_TIMEOUT_SECONDS,
                )
            self._thread = None

    @property
    def error(self) -> RecognizerError | None:
        """Error de inferencia capturado en el worker, si lo hubo."""
        return self._error

    def __enter__(self) -> "_RecognitionWorker":
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stop()


def _request_name(*, reader: Callable[[str], str] | None = None) -> str:
    """Pide el nombre antes de abrir la camara; vacio si se cancelo."""
    LOGGER.info("Enrolamiento: escribe tu nombre y pulsa Enter (Ctrl+C cancela).")
    ask = reader if reader is not None else input
    try:
        return ask(NAME_PROMPT).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _request_role(*, reader: Callable[[str], str] | None = None) -> str:
    """Pide el rol del nuevo rostro; vacio si se cancelo o se acepta el defecto."""
    ask = reader if reader is not None else input
    try:
        return ask(ROLE_PROMPT).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return ""


def _resolve_enroll_role(
    *,
    operator: Identity,
    is_first: bool,
    face_config: FaceAuthConfig,
    reader: Callable[[str], str] | None = None,
) -> Role | None:
    """Rol del nuevo enrolado segun quien opera; ``None`` si no tiene permiso.

    El primer rostro del almacen es admin automaticamente. Un admin elige
    cualquier rol (defecto: el de config); un operator solo operator/viewer;
    viewer e invitados no pueden enrolar.
    """
    if is_first:
        LOGGER.info("Primer rostro del almacen: se asigna rol admin.")
        return Role.ADMIN
    match operator.role:
        case Role.ADMIN:
            choice = _request_role(reader=reader)
            match choice:
                case "":
                    return face_config.default_role
                case "admin":
                    return Role.ADMIN
                case "operator":
                    return Role.OPERATOR
                case "viewer":
                    return Role.VIEWER
                case _:
                    LOGGER.warning("Rol no valido %r; se usa operator.", choice)
                    return Role.OPERATOR
        case Role.OPERATOR:
            choice = _request_role(reader=reader)
            match choice:
                case "admin":
                    LOGGER.error("Sin permiso: un operator no puede enrolar admins.")
                    return None
                case "viewer":
                    return Role.VIEWER
                case _:
                    if choice not in ("", "operator"):
                        LOGGER.warning("Rol no valido %r; se usa operator.", choice)
                    return Role.OPERATOR
        case _:
            LOGGER.error("Sin permiso para enrolar: se requiere operator o admin.")
            return None


def _identity_provider(
    face_config: FaceAuthConfig, repository: FileFaceRepository
) -> FileIdentityProvider:
    """Proveedor de sesion sobre el mismo directorio del almacen de rostros."""
    return FileIdentityProvider(
        face_config.store_dir,
        repository,
        session_timeout_seconds=face_config.session_timeout_seconds,
    )


def run_face_enroll(request: AppRunRequest, *, reader: Callable[[str], str] | None = None) -> int:
    """Enrola un rostro nuevo con guia de angulos y distancia.

    Devuelve 0 si termino bien (ESC/q vuelve al menu), 1 si fallo.
    """
    show_window = request.show_window
    alert = SilentAlert()
    try:
        if not show_window and request.max_frames <= 0:
            msg = "Sin ventana no hay ESC: usa --frames > 0 junto con --no-window."
            raise RecognizerError(msg)
        name = _request_name(reader=reader)
        if not name:
            LOGGER.error("Enrolamiento cancelado: se requiere un nombre no vacio.")
            return 1
        with log_step(LOGGER, "Cargando configuracion"):
            config_path = prepare_workspace(request.config_path)
            app_config = load_config(config_path)
            camera_config = resolve_camera_config(
                app_config=app_config, device_override=request.device
            )
            face_config = app_config.face_auth
        builder = EnrollmentBuilder(
            samples_required=face_config.enrollment_samples,
            min_width=face_config.min_face_width_ratio,
            max_width=face_config.max_face_width_ratio,
            min_sharpness=face_config.min_sharpness,
        )
        repository = FileFaceRepository(face_config.store_dir)
        operator = _identity_provider(face_config, repository).current_identity()
        is_first = len(repository.list_all()) == 0
        role = _resolve_enroll_role(
            operator=operator, is_first=is_first, face_config=face_config, reader=reader
        )
        if role is None:
            return 1
        face_id = repository.next_id()
        recognizer = InsightFaceRecognizer(face_config)
        pipeline = PipelineBuilder().build()
        state = _EnrollState(required=face_config.enrollment_samples)
        LOGGER.info(
            "Enrolando a %s (%s, rol %s): centra la cara y sigue las instrucciones.",
            name,
            face_id,
            role.value,
        )

        lock = threading.Lock()

        def _process(observations: tuple[FaceObservation, ...]) -> None:
            """Actualiza el enrolamiento con las observaciones del worker."""
            with lock:
                if not observations:
                    state.guidance = CaptureGuidance.CENTER_FACE
                    state.boxes = ()
                else:
                    observation = observations[0]
                    state.boxes = (observation.box,)
                    state.guidance = builder.add(observation)
                    state.accepted = builder.accepted
                if builder.is_complete and not state.saved:
                    enrolled = builder.build(face_id, name, role=role)
                    repository.save(enrolled)
                    state.saved = True
                    LOGGER.info(
                        "Rostro enrolado: %s (%s, rol %s). Pulsa ESC para volver.",
                        name,
                        face_id,
                        role.value,
                    )

        def _on_context(context: FrameContext) -> None:
            if worker.error is not None:
                raise worker.error
            with lock:
                boxes = state.boxes
                guidance = state.guidance
                accepted = state.accepted
                saved = state.saved
                complete = builder.is_complete
                step = builder.current_step()
            progress = (
                f"{name}: {accepted}/{state.required} - {step.prompt}"
                if not saved
                else f"{name}: completo, pulsa ESC"
            )
            draw_face_overlay(
                context.frame.data,
                boxes=boxes,
                guidance=guidance,
                progress_text=progress,
                login_text="",
                highlight_ok=complete,
                target_width_ratio=face_config.min_face_width_ratio,
            )

        def _on_progress(count: int, fps: float) -> None:
            with lock:
                accepted = state.accepted
            LOGGER.info(
                "Fotogramas: %d | FPS medio: %.1f | Muestras: %d/%d",
                count,
                fps,
                accepted,
                state.required,
            )

        with ExitStack() as stack:
            with log_step(LOGGER, f"Abriendo camara (device={camera_config.device_index})"):
                camera = stack.enter_context(OpenCVCamera(camera_config))
            source = stack.enter_context(LatestFrameSource(camera))
            with log_step(LOGGER, f"Cargando modelo facial ({face_config.model_path})"):
                stack.enter_context(recognizer)
            stack.enter_context(alert)
            worker = stack.enter_context(
                _RecognitionWorker(
                    source=source,
                    recognizer=recognizer,
                    process=_process,
                    process_every_n_frames=face_config.process_every_n_frames,
                    logger=LOGGER,
                )
            )
            LOGGER.info("Listo. Pulsa ESC o q para volver al menu.")
            frames, fps = run_camera_loop(
                source,
                pipeline=pipeline,
                window_name=ENROLL_WINDOW_NAME,
                show_window=show_window,
                max_frames=request.max_frames,
                callbacks=RuntimeCallbacks(on_context=_on_context, on_progress=_on_progress),
            )
    except RecognizerError as exc:
        LOGGER.error("La app fallo: %s", exc)
        return 1
    except Exception:
        LOGGER.exception("Error inesperado en el enrolamiento facial")
        return 1
    finally:
        alert.close()
        if show_window:
            cv2.destroyAllWindows()
    LOGGER.info("Enrolamiento OK: %d fotogramas, %.1f FPS medio.", frames, fps)
    return 0


def run_face_login(request: AppRunRequest) -> int:
    """Saluda al reconocer un rostro enrolado (edge-triggered con debounce).

    Devuelve 0 si termino bien (ESC/q vuelve al menu), 1 si fallo.
    """
    show_window = request.show_window
    alert = SilentAlert()
    try:
        if not show_window and request.max_frames <= 0:
            msg = "Sin ventana no hay ESC: usa --frames > 0 junto con --no-window."
            raise RecognizerError(msg)
        with log_step(LOGGER, "Cargando configuracion"):
            config_path = prepare_workspace(request.config_path)
            app_config = load_config(config_path)
            camera_config = resolve_camera_config(
                app_config=app_config, device_override=request.device
            )
            face_config = app_config.face_auth
        repository = FileFaceRepository(face_config.store_dir)
        enrolled = repository.list_all()
        if not enrolled:
            LOGGER.error("Sin rostros enrolados: usa primero la opcion Enrolar.")
            return 1
        session_provider = _identity_provider(face_config, repository)
        matcher = FaceMatcher(threshold=face_config.match_threshold)
        debouncer = LoginDebouncer(
            confirm_frames=face_config.confirm_frames,
            release_frames=face_config.release_frames,
        )
        recognizer = InsightFaceRecognizer(face_config)
        pipeline = PipelineBuilder().build()
        state = _LoginState()
        enrolled_tuple = tuple(enrolled)
        LOGGER.info("Login facial: %d rostro(s) conocido(s).", len(enrolled_tuple))

        lock = threading.Lock()

        def _process(observations: tuple[FaceObservation, ...]) -> None:
            """Actualiza el login (matching, debounce y sesion) en el worker."""
            greet: EnrolledFace | None = None
            with lock:
                if not observations:
                    state.boxes = ()
                    state.guidance = None
                    identity = debouncer.update(
                        FaceMatch(face=None, distance=NO_FACE_DISTANCE, accepted=False)
                    )
                else:
                    observation = observations[0]
                    state.boxes = (observation.box,)
                    state.guidance = assess_capture(
                        observation.box,
                        observation.sharpness,
                        min_width=face_config.min_face_width_ratio,
                        max_width=face_config.max_face_width_ratio,
                        min_sharpness=face_config.min_sharpness,
                    )
                    match = matcher.identify(observation.embedding, enrolled_tuple)
                    identity = debouncer.update(match)
                    if not match.accepted:
                        state.login_text = UNKNOWN_TEXT
                    elif identity is None:
                        state.login_text = RECOGNIZING_TEXT
                if identity is not None:
                    state.highlight_ok = True
                    state.login_text = f"Bienvenido {identity.name} {identity.face_id}"
                    if state.greeted_id != identity.face_id:
                        state.greeted_id = identity.face_id
                        greet = identity
                elif not observations:
                    state.highlight_ok = False
                    state.login_text = ""
                else:
                    state.highlight_ok = False
            if greet is not None:
                # I/O a disco fuera del lock: no debe frenar el dibujo.
                _write_login_session(session_provider, greet)

        def _on_context(context: FrameContext) -> None:
            if worker.error is not None:
                raise worker.error
            with lock:
                boxes = state.boxes
                guidance = state.guidance
                login_text = state.login_text
                highlight_ok = state.highlight_ok
            draw_face_overlay(
                context.frame.data,
                boxes=boxes,
                guidance=guidance,
                progress_text=f"Rostros conocidos: {len(enrolled_tuple)}",
                login_text=login_text,
                highlight_ok=highlight_ok,
                target_width_ratio=face_config.min_face_width_ratio,
            )

        def _on_progress(count: int, fps: float) -> None:
            with lock:
                login_text = state.login_text
            LOGGER.info(
                "Fotogramas: %d | FPS medio: %.1f | %s",
                count,
                fps,
                login_text if login_text else "buscando rostro",
            )

        with ExitStack() as stack:
            with log_step(LOGGER, f"Abriendo camara (device={camera_config.device_index})"):
                camera = stack.enter_context(OpenCVCamera(camera_config))
            source = stack.enter_context(LatestFrameSource(camera))
            with log_step(LOGGER, f"Cargando modelo facial ({face_config.model_path})"):
                stack.enter_context(recognizer)
            stack.enter_context(alert)
            worker = stack.enter_context(
                _RecognitionWorker(
                    source=source,
                    recognizer=recognizer,
                    process=_process,
                    process_every_n_frames=face_config.process_every_n_frames,
                    logger=LOGGER,
                )
            )
            LOGGER.info("Listo. Pulsa ESC o q para volver al menu.")
            frames, fps = run_camera_loop(
                source,
                pipeline=pipeline,
                window_name=LOGIN_WINDOW_NAME,
                show_window=show_window,
                max_frames=request.max_frames,
                callbacks=RuntimeCallbacks(on_context=_on_context, on_progress=_on_progress),
            )
    except RecognizerError as exc:
        LOGGER.error("La app fallo: %s", exc)
        return 1
    except Exception:
        LOGGER.exception("Error inesperado en el login facial")
        return 1
    finally:
        alert.close()
        if show_window:
            cv2.destroyAllWindows()
    LOGGER.info("Login OK: %d fotogramas, %.1f FPS medio.", frames, fps)
    return 0


def _write_login_session(session_provider: FileIdentityProvider, identity: EnrolledFace) -> None:
    """Persiste la sesion tras el saludo (edge-triggered) o avisa si falla."""
    try:
        session_provider.write_session(identity)
    except RecognizerError as exc:
        LOGGER.warning("Login sin sesion persistida (%s).", exc)
        return
    LOGGER.info("Bienvenido %s %s", identity.name, identity.face_id)
    LOGGER.info("Sesion iniciada: %s (%s)", identity.name, identity.role.value)


def run_face_logout(request: AppRunRequest) -> int:
    """Borra la sesion facial; devuelve 0 siempre que el almacen responda."""
    try:
        with log_step(LOGGER, "Cargando configuracion"):
            config_path = prepare_workspace(request.config_path)
            app_config = load_config(config_path)
            face_config = app_config.face_auth
        repository = FileFaceRepository(face_config.store_dir)
        _identity_provider(face_config, repository).clear_session()
    except RecognizerError as exc:
        LOGGER.error("No se pudo cerrar la sesion: %s", exc)
        return 1
    except Exception:
        LOGGER.exception("Error inesperado al cerrar la sesion facial")
        return 1
    LOGGER.info("Sesion cerrada.")
    return 0


def run_face_auth(request: AppRunRequest) -> int:
    """Submenu facial: 1 Enrolar, 2 Login, 3 Cerrar sesion, 0 Volver."""
    while True:
        LOGGER.info(AUTH_MENU_TEXT)
        try:
            choice = input(AUTH_PROMPT).strip()
        except (EOFError, KeyboardInterrupt):
            LOGGER.info("Volviendo al menu principal.")
            return 0
        match choice:
            case "1":
                return run_face_enroll(request)
            case "2":
                return run_face_login(request)
            case "3":
                return run_face_logout(request)
            case "0" | "q" | "salir" | "exit":
                return 0
            case _:
                LOGGER.warning("Opcion no valida: %r", choice)
                continue
