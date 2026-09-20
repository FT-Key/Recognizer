"""App Contador de vehiculos: tracking YOLO + conteo de cruces de linea.

Usa una sola via de inferencia (`model.track`, que ya incluye la deteccion) y
cuenta entradas/salidas al cruzar una linea configurable. Reutiliza
`LineCrossingCounter` y `UltralyticsDetector` del contador de personas.
"""

import logging
from contextlib import ExitStack
from dataclasses import dataclass

import cv2

from recognizer.adapters.camera_opencv import OpenCVCamera
from recognizer.adapters.overlay_vehicle import draw_vehicle_overlay
from recognizer.adapters.ultralytics_detector import UltralyticsDetector
from recognizer.bootstrap import resolve_camera_config
from recognizer.cli.console import log_step
from recognizer.cli.paths import prepare_workspace
from recognizer.cli.runtime import RuntimeCallbacks, run_camera_loop
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.domain.tracking import CountingLine, LineCrossingCounter
from recognizer.core.errors import RecognizerError
from recognizer.core.pipeline.builder import PipelineBuilder
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.ports.object_tracker import ObjectTracker
from recognizer.settings import load_config

LOGGER = logging.getLogger("recognizer.vehicle_counter")

WINDOW_NAME = "Contador de vehiculos"


@dataclass
class _HudState:
    """Estado mutable compartido por los callbacks del bucle de camara."""

    current: int = 0
    entries: int = 0
    exits: int = 0


def run_vehicle_counter(request: AppRunRequest) -> int:
    """Ejecuta el contador de vehiculos.

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
            vehicle_config = app_config.vehicle_counter
        line_config = vehicle_config.line
        line_obj = (
            CountingLine(
                axis=line_config.axis,
                position=line_config.position,
                margin=line_config.margin,
            )
            if line_config.enabled
            else None
        )
        counter = (
            LineCrossingCounter(
                line=line_obj,
                invert=line_config.invert,
                confirm_frames=line_config.confirm_frames,
                track_timeout_frames=line_config.track_timeout_frames,
            )
            if line_obj is not None
            else None
        )
        pipeline = PipelineBuilder().build()
        detector = UltralyticsDetector(vehicle_config)
        tracker: ObjectTracker = detector
        state = _HudState()

        def _on_context(context: FrameContext) -> None:
            tracked = tracker.track(context.frame)
            vehicles = tuple(item for item in tracked if item.label == vehicle_config.target_label)
            state.current = len(vehicles)
            if counter is not None:
                snapshot = counter.update(vehicles)
                state.entries = snapshot.entries
                state.exits = snapshot.exits
            draw_vehicle_overlay(
                context.frame.data,
                tracked=vehicles,
                current=state.current,
                entries=state.entries,
                exits=state.exits,
                line=line_obj,
            )

        def _on_progress(count: int, fps: float) -> None:
            LOGGER.info(
                "Fotogramas: %d | FPS medio: %.1f | Vehiculos: %d | Entradas: %d | Salidas: %d",
                count,
                fps,
                state.current,
                state.entries,
                state.exits,
            )

        with ExitStack() as stack:
            with log_step(LOGGER, f"Abriendo camara (device={camera_config.device_index})"):
                camera = stack.enter_context(OpenCVCamera(camera_config))
            with log_step(LOGGER, f"Cargando modelo YOLO ({vehicle_config.model_path})"):
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
        LOGGER.exception("Error inesperado en el contador de vehiculos")
        return 1
    finally:
        if show_window:
            cv2.destroyAllWindows()

    LOGGER.info(
        "App OK: %d fotogramas, %.1f FPS medio, vehiculos: %d, entradas: %d, salidas: %d.",
        frames,
        fps,
        state.current,
        state.entries,
        state.exits,
    )
    return 0
