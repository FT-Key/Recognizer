"""App Reconocimiento facial: enrolamiento y login con InsightFace.

Una sola via de inferencia (InsightFace buffalo en CPU): cada fotograma se
reconoce una sola vez en ``on_context`` y el overlay dibuja el resultado. Al
salir (ESC/q) devuelve el control al launcher.
"""

import logging
from contextlib import ExitStack
from dataclasses import dataclass

import cv2

from recognizer.adapters.alert_sound import SilentAlert
from recognizer.adapters.camera_opencv import OpenCVCamera
from recognizer.adapters.file_face_repository import FileFaceRepository
from recognizer.adapters.insightface_recognizer import InsightFaceRecognizer
from recognizer.adapters.overlay_face import draw_face_overlay
from recognizer.bootstrap import resolve_camera_config
from recognizer.cli.console import log_step
from recognizer.cli.paths import prepare_workspace
from recognizer.cli.runtime import RuntimeCallbacks, run_camera_loop
from recognizer.core.constants import FACE_MAX_COSINE_DISTANCE
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.domain.face import (
    CaptureGuidance,
    EnrollmentBuilder,
    FaceBox,
    FaceMatch,
    FaceMatcher,
    LoginDebouncer,
    assess_capture,
)
from recognizer.core.errors import RecognizerError
from recognizer.core.pipeline.builder import PipelineBuilder
from recognizer.core.pipeline.context import FrameContext
from recognizer.settings import load_config

LOGGER = logging.getLogger("recognizer.face_auth")

ENROLL_WINDOW_NAME = "Enrolamiento facial"
LOGIN_WINDOW_NAME = "Login facial"
AUTH_MENU_TEXT = "1) Enrolar rostro  2) Login facial  0) Volver"
AUTH_PROMPT = "Elige (1/2/0): "
NAME_PROMPT = "Nombre para enrolar: "
NO_FACE_DISTANCE = FACE_MAX_COSINE_DISTANCE
UNKNOWN_TEXT = "Desconocido"


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


def _request_name() -> str:
    """Pide el nombre antes de abrir la camara; vacio si se cancelo."""
    LOGGER.info("Enrolamiento: escribe tu nombre y pulsa Enter (Ctrl+C cancela).")
    try:
        return input(NAME_PROMPT).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def run_face_enroll(request: AppRunRequest) -> int:
    """Enrola un rostro nuevo con guia de angulos y distancia.

    Devuelve 0 si termino bien (ESC/q vuelve al menu), 1 si fallo.
    """
    show_window = request.show_window
    alert = SilentAlert()
    try:
        if not show_window and request.max_frames <= 0:
            msg = "Sin ventana no hay ESC: usa --frames > 0 junto con --no-window."
            raise RecognizerError(msg)
        name = _request_name()
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
        face_id = repository.next_id()
        recognizer = InsightFaceRecognizer(face_config)
        pipeline = PipelineBuilder().build()
        state = _EnrollState(required=face_config.enrollment_samples)
        LOGGER.info(
            "Enrolando a %s (%s): centra la cara y sigue las instrucciones.",
            name,
            face_id,
        )

        def _on_context(context: FrameContext) -> None:
            observations = recognizer.recognize(context.frame)
            if not observations:
                state.guidance = CaptureGuidance.CENTER_FACE
                state.boxes = ()
            else:
                observation = observations[0]
                state.boxes = (observation.box,)
                result = builder.add(observation)
                state.guidance = result
                state.accepted = builder.accepted
            step = builder.current_step()
            progress = (
                f"{name}: {state.accepted}/{state.required} - {step.prompt}"
                if not state.saved
                else f"{name}: completo, pulsa ESC"
            )
            draw_face_overlay(
                context.frame.data,
                boxes=state.boxes,
                guidance=state.guidance,
                progress_text=progress,
                login_text="",
                highlight_ok=builder.is_complete,
            )
            if builder.is_complete and not state.saved:
                enrolled = builder.build(face_id, name)
                repository.save(enrolled)
                state.saved = True
                LOGGER.info("Rostro enrolado: %s (%s). Pulsa ESC para volver.", name, face_id)

        def _on_progress(count: int, fps: float) -> None:
            LOGGER.info(
                "Fotogramas: %d | FPS medio: %.1f | Muestras: %d/%d",
                count,
                fps,
                state.accepted,
                state.required,
            )

        with ExitStack() as stack:
            with log_step(LOGGER, f"Abriendo camara (device={camera_config.device_index})"):
                camera = stack.enter_context(OpenCVCamera(camera_config))
            with log_step(LOGGER, f"Cargando modelo facial ({face_config.model_path})"):
                stack.enter_context(recognizer)
            stack.enter_context(alert)
            LOGGER.info("Listo. Pulsa ESC o q para volver al menu.")
            frames, fps = run_camera_loop(
                camera,
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

        def _on_context(context: FrameContext) -> None:
            observations = recognizer.recognize(context.frame)
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
                    state.login_text = "Reconociendo..."
            if identity is not None:
                state.highlight_ok = True
                state.login_text = f"Bienvenido {identity.name} {identity.face_id}"
                if state.greeted_id != identity.face_id:
                    state.greeted_id = identity.face_id
                    LOGGER.info("Bienvenido %s %s", identity.name, identity.face_id)
            elif not observations:
                state.highlight_ok = False
                state.login_text = ""
            else:
                state.highlight_ok = False
            draw_face_overlay(
                context.frame.data,
                boxes=state.boxes,
                guidance=state.guidance,
                progress_text=f"Rostros conocidos: {len(enrolled_tuple)}",
                login_text=state.login_text,
                highlight_ok=state.highlight_ok,
            )

        def _on_progress(count: int, fps: float) -> None:
            LOGGER.info(
                "Fotogramas: %d | FPS medio: %.1f | %s",
                count,
                fps,
                state.login_text if state.login_text else "buscando rostro",
            )

        with ExitStack() as stack:
            with log_step(LOGGER, f"Abriendo camara (device={camera_config.device_index})"):
                camera = stack.enter_context(OpenCVCamera(camera_config))
            with log_step(LOGGER, f"Cargando modelo facial ({face_config.model_path})"):
                stack.enter_context(recognizer)
            stack.enter_context(alert)
            LOGGER.info("Listo. Pulsa ESC o q para volver al menu.")
            frames, fps = run_camera_loop(
                camera,
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


def run_face_auth(request: AppRunRequest) -> int:
    """Submenu facial: 1 Enrolar, 2 Login, 0 Volver al menu principal."""
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
            case "0" | "q" | "salir" | "exit":
                return 0
            case _:
                LOGGER.warning("Opcion no valida: %r", choice)
                continue
