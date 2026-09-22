"""App Edad y genero: estima edad y genero de los rostros en vivo.

Una sola via de inferencia: el estimador facial de InsightFace (deteccion +
genderage, sin embeddings). Cada fotograma estima los atributos, los suaviza por
rostro y los dibuja; ESC/q vuelve al menu. No guarda imagenes ni identidades.
"""

import logging
from contextlib import ExitStack
from dataclasses import dataclass

import cv2

from recognizer.adapters.camera_opencv import OpenCVCamera
from recognizer.adapters.insightface_attributes import InsightFaceAttributeEstimator
from recognizer.adapters.overlay_gender_age import draw_gender_age_overlay
from recognizer.bootstrap import resolve_camera_config
from recognizer.cli.console import log_step
from recognizer.cli.paths import prepare_workspace
from recognizer.cli.runtime import RuntimeCallbacks, run_camera_loop
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.domain.face_attributes import AgeGenderSmoother
from recognizer.core.errors import RecognizerError
from recognizer.core.pipeline.builder import PipelineBuilder
from recognizer.core.pipeline.context import FrameContext
from recognizer.settings import load_config

LOGGER = logging.getLogger("recognizer.gender_age")

WINDOW_NAME = "Edad y genero"


@dataclass
class _HudState:
    """Estado mutable compartido por los callbacks del bucle de camara."""

    faces: int = 0


def run_gender_age(request: AppRunRequest) -> int:
    """Ejecuta la estimacion de edad y genero.

    Pensada para el launcher: al salir (ESC/q) devuelve el control al llamador
    en lugar de terminar el proceso. Devuelve 0 si termino bien, 1 si fallo.
    """
    show_window = request.show_window

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
            gender_age_config = app_config.gender_age
        pipeline = PipelineBuilder().build()
        estimator = InsightFaceAttributeEstimator(gender_age_config)
        smoother = AgeGenderSmoother(window=gender_age_config.smoothing_window)
        state = _HudState()

        def _on_context(context: FrameContext) -> None:
            faces = smoother.update(estimator.estimate(context.frame))
            state.faces = len(faces)
            draw_gender_age_overlay(context.frame.data, faces=faces)

        def _on_progress(count: int, fps: float) -> None:
            LOGGER.info(
                "Fotogramas: %d | FPS medio: %.1f | Rostros: %d",
                count,
                fps,
                state.faces,
            )

        with ExitStack() as stack:
            with log_step(LOGGER, f"Abriendo camara (device={camera_config.device_index})"):
                camera = stack.enter_context(OpenCVCamera(camera_config))
            with log_step(
                LOGGER, f"Cargando detector de edad/genero ({gender_age_config.model_path})"
            ):
                stack.enter_context(estimator)
            LOGGER.info("Listo. Pulsa ESC o q para volver al menu.")
            frames, fps = run_camera_loop(
                camera,
                pipeline=pipeline,
                window_name=WINDOW_NAME,
                show_window=show_window,
                max_frames=request.max_frames,
                callbacks=RuntimeCallbacks(
                    on_context=_on_context,
                    on_progress=_on_progress,
                ),
            )
    except RecognizerError as exc:
        LOGGER.error("La app fallo: %s", exc)
        return 1
    except Exception:
        LOGGER.exception("Error inesperado en la estimacion de edad/genero")
        return 1
    finally:
        if show_window:
            cv2.destroyAllWindows()

    LOGGER.info(
        "App OK: %d fotogramas, %.1f FPS medio, rostros en el ultimo fotograma: %d.",
        frames,
        fps,
        state.faces,
    )
    return 0
