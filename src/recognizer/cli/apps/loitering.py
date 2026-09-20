"""App Loitering: detecta personas que permanecen en una zona mas de N segundos.

Usa una sola via de inferencia (`model.track`, que incluye la deteccion) y el
dominio puro `ZoneLoiteringMonitor` para acumular dwell time por track_id. La
alerta se dispara al exceder el umbral y se repite segun `loitering.alert`.
"""

import logging
import time
from contextlib import ExitStack
from dataclasses import dataclass, field

import cv2

from recognizer.adapters.alert_sound import SilentAlert, SystemSoundAlert
from recognizer.adapters.camera_opencv import OpenCVCamera
from recognizer.adapters.overlay_loitering import draw_loitering_overlay
from recognizer.adapters.ultralytics_detector import UltralyticsDetector
from recognizer.bootstrap import resolve_camera_config
from recognizer.cli.console import log_step
from recognizer.cli.paths import prepare_workspace
from recognizer.cli.runtime import RuntimeCallbacks, run_camera_loop
from recognizer.core.config import LoiteringAlertConfig
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.domain.loitering import (
    LoiteringSnapshot,
    LoiteringZone,
    ZoneLoiteringMonitor,
)
from recognizer.core.errors import RecognizerError
from recognizer.core.pipeline.builder import PipelineBuilder
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.ports.alert_sink import AlertSink
from recognizer.core.ports.object_tracker import ObjectTracker
from recognizer.settings import load_config

LOGGER = logging.getLogger("recognizer.loitering")

WINDOW_NAME = "Zona permanencia"


@dataclass
class _MonitorState:
    """Estado mutable compartido por los callbacks del bucle de camara."""

    loiterers: int = 0
    loiterer_ids: tuple[int, ...] = ()
    dwell_times: dict[int, float] = field(default_factory=dict)
    alerting: bool = False
    last_notified: float = 0.0
    current_fps: float = 30.0


def _apply_alert(
    *,
    snapshot: LoiteringSnapshot,
    alert: AlertSink,
    config: LoiteringAlertConfig,
    state: _MonitorState,
    now: float,
) -> None:
    """Dispara la alerta al exceder el dwell y la repite mientras dure."""
    if not snapshot.active:
        state.alerting = False
        return
    if not state.alerting:
        state.alerting = True
        state.last_notified = now
        alert.notify()
        return
    if config.repeat_seconds > 0 and now - state.last_notified >= config.repeat_seconds:
        state.last_notified = now
        alert.notify()


def run_loitering(request: AppRunRequest) -> int:
    """Ejecuta la app de zona permanencia.

    Pensada para el launcher: al salir (ESC/q) devuelve el control al llamador
    en lugar de terminar el proceso. Devuelve 0 si termino bien, 1 si fallo.
    """
    show_window = request.show_window
    alert: SystemSoundAlert | SilentAlert = SilentAlert()

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
            loitering_config = app_config.loitering
        zone_config = loitering_config.zone
        zone_obj = (
            LoiteringZone(
                x_min=zone_config.x_min,
                y_min=zone_config.y_min,
                x_max=zone_config.x_max,
                y_max=zone_config.y_max,
            )
            if zone_config.enabled
            else None
        )
        monitor = (
            ZoneLoiteringMonitor(
                zone=zone_obj,
                dwell_threshold_seconds=loitering_config.dwell_threshold_seconds,
                confirm_frames=zone_config.confirm_frames,
                release_frames=zone_config.release_frames,
            )
            if zone_obj is not None
            else None
        )
        pipeline = PipelineBuilder().build()
        detector = UltralyticsDetector(loitering_config)
        tracker: ObjectTracker = detector
        alert = SystemSoundAlert() if loitering_config.alert.enabled else SilentAlert()
        state = _MonitorState()

        def _on_context(context: FrameContext) -> None:
            tracked = tracker.track(context.frame)
            people = tuple(item for item in tracked if item.label == loitering_config.target_label)
            if monitor is not None:
                snapshot = monitor.update(people, fps=state.current_fps)
                state.loiterers = snapshot.count
                state.loiterer_ids = snapshot.loiterer_ids
                state.dwell_times = snapshot.dwell_times
                _apply_alert(
                    snapshot=snapshot,
                    alert=alert,
                    config=loitering_config.alert,
                    state=state,
                    now=time.monotonic(),
                )
            draw_loitering_overlay(
                context.frame.data,
                tracked=people,
                zone=zone_obj,
                active=state.alerting,
                loiterer_ids=frozenset(state.loiterer_ids),
                dwell_times=state.dwell_times,
                threshold=loitering_config.dwell_threshold_seconds,
            )

        def _on_progress(count: int, fps: float) -> None:
            state.current_fps = fps if fps > 0 else 30.0
            LOGGER.info(
                "Fotogramas: %d | FPS medio: %.1f | Loiterers: %d | Alerta: %s",
                count,
                fps,
                state.loiterers,
                "si" if state.alerting else "no",
            )

        with ExitStack() as stack:
            with log_step(LOGGER, f"Abriendo camara (device={camera_config.device_index})"):
                camera = stack.enter_context(OpenCVCamera(camera_config))
            with log_step(LOGGER, f"Cargando modelo YOLO ({loitering_config.model_path})"):
                stack.enter_context(detector)
            stack.enter_context(alert)
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
        LOGGER.exception("Error inesperado en la zona permanencia")
        return 1
    finally:
        alert.close()
        if show_window:
            cv2.destroyAllWindows()

    LOGGER.info(
        "App OK: %d fotogramas, %.1f FPS medio, loiterers finales: %d.",
        frames,
        fps,
        state.loiterers,
    )
    return 0
