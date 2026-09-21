"""App Desenfoque privacidad: difumina los rostros en vivo.

Una sola via de inferencia: el detector facial de InsightFace (solo deteccion,
sin embeddings). Cada fotograma detecta los rostros y los difumina antes de
mostrarlo; ESC/q vuelve al menu. No guarda imagenes ni identidades.
"""

import logging
from contextlib import ExitStack
from dataclasses import dataclass

import cv2

from recognizer.adapters.camera_opencv import OpenCVCamera
from recognizer.adapters.insightface_detector import InsightFaceFaceDetector
from recognizer.adapters.overlay_privacy import blur_faces, draw_privacy_overlay
from recognizer.bootstrap import resolve_camera_config
from recognizer.cli.console import log_step
from recognizer.cli.paths import prepare_workspace
from recognizer.cli.runtime import RuntimeCallbacks, run_camera_loop
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.errors import RecognizerError
from recognizer.core.pipeline.builder import PipelineBuilder
from recognizer.core.pipeline.context import FrameContext
from recognizer.settings import load_config

LOGGER = logging.getLogger("recognizer.privacy_blur")

WINDOW_NAME = "Desenfoque privacidad"


@dataclass
class _HudState:
    """Estado mutable compartido por los callbacks del bucle de camara."""

    faces: int = 0


def run_privacy_blur(request: AppRunRequest) -> int:
    """Ejecuta el desenfoque de privacidad.

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
            privacy_config = app_config.privacy_blur
        pipeline = PipelineBuilder().build()
        detector = InsightFaceFaceDetector(privacy_config)
        state = _HudState()

        def _on_context(context: FrameContext) -> None:
            faces = detector.detect(context.frame)
            state.faces = len(faces)
            regions = blur_faces(
                context.frame.data,
                boxes=faces,
                blur_strength=privacy_config.blur_strength,
                margin_ratio=privacy_config.margin_ratio,
            )
            draw_privacy_overlay(context.frame.data, regions=regions, blurred=len(regions))

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
            with log_step(LOGGER, f"Cargando detector facial ({privacy_config.model_path})"):
                stack.enter_context(detector)
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
        LOGGER.exception("Error inesperado en el desenfoque de privacidad")
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
