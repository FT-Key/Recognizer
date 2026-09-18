"""App Contador de personas: deteccion YOLO + conteo (sin tracking).

El tracking, la zona/linea y su overlay llegan en la etapa 10c; aqui solo se
detecta y se cuenta por fotograma.
"""

import logging
from contextlib import ExitStack

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.adapters.camera_opencv import OpenCVCamera
from recognizer.adapters.ultralytics_detector import UltralyticsDetector
from recognizer.bootstrap import resolve_camera_config
from recognizer.cli.console import log_step
from recognizer.cli.paths import prepare_workspace
from recognizer.cli.runtime import RuntimeCallbacks, run_camera_loop
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.domain.detection import Detection, count_people
from recognizer.core.errors import RecognizerError
from recognizer.core.pipeline.builder import PipelineBuilder
from recognizer.core.pipeline.context import FrameContext
from recognizer.settings import load_config

LOGGER = logging.getLogger("recognizer.people_counter")

WINDOW_NAME = "Contador de personas"
HUD_POSITION = (10, 30)
HUD_FONT = cv2.FONT_HERSHEY_SIMPLEX
HUD_SCALE = 0.9
HUD_THICKNESS = 2
HUD_COLOR_BGR = (0, 200, 0)
BOX_COLOR_BGR = (0, 200, 0)
BOX_THICKNESS = 2
BOX_LABEL_SCALE = 0.6
BOX_LABEL_THICKNESS = 1
BOX_LABEL_MARGIN_PX = 6


def _draw_overlay(
    image: NDArray[np.uint8],
    *,
    detections: tuple[Detection, ...],
    total: int,
    width: int,
    height: int,
) -> None:
    """Dibuja las cajas detectadas y el HUD con el conteo (en su sitio)."""
    for detection in detections:
        x_min = int(detection.bbox.x_min * width)
        y_min = int(detection.bbox.y_min * height)
        x_max = int(detection.bbox.x_max * width)
        y_max = int(detection.bbox.y_max * height)
        cv2.rectangle(image, (x_min, y_min), (x_max, y_max), BOX_COLOR_BGR, BOX_THICKNESS)
        cv2.putText(
            image,
            f"{detection.label} {detection.confidence:.2f}",
            (x_min, max(y_min - BOX_LABEL_MARGIN_PX, 0)),
            HUD_FONT,
            BOX_LABEL_SCALE,
            BOX_COLOR_BGR,
            BOX_LABEL_THICKNESS,
        )
    cv2.putText(
        image,
        f"Personas: {total}",
        HUD_POSITION,
        HUD_FONT,
        HUD_SCALE,
        HUD_COLOR_BGR,
        HUD_THICKNESS,
    )


def run_people_counter(request: AppRunRequest) -> int:
    """Ejecuta el contador de personas.

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
            people_config = app_config.people_counter
        pipeline = PipelineBuilder().build()
        detector = UltralyticsDetector(people_config)
        state = {"count": 0}

        def _on_context(context: FrameContext) -> None:
            detections = detector.detect(context.frame)
            total = count_people(detections, label=people_config.target_label)
            state["count"] = total
            _draw_overlay(
                context.frame.data,
                detections=detections,
                total=total,
                width=context.frame.width,
                height=context.frame.height,
            )

        def _on_progress(count: int, fps: float) -> None:
            LOGGER.info(
                "Fotogramas: %d | FPS medio: %.1f | Personas: %d",
                count,
                fps,
                state["count"],
            )

        with ExitStack() as stack:
            with log_step(LOGGER, f"Abriendo camara (device={camera_config.device_index})"):
                camera = stack.enter_context(OpenCVCamera(camera_config))
            with log_step(LOGGER, f"Cargando modelo YOLO ({people_config.model_path})"):
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
        LOGGER.exception("Error inesperado en el contador de personas")
        return 1
    finally:
        if show_window:
            cv2.destroyAllWindows()

    LOGGER.info(
        "App OK: %d fotogramas, %.1f FPS medio, personas en el ultimo fotograma: %d.",
        frames,
        fps,
        state["count"],
    )
    return 0
