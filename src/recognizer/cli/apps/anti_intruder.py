"""App Anti-intrusos: detecta personas en una zona y dispara una alerta.

Usa una sola via de inferencia (`model.track`, que incluye la deteccion) y el
dominio puro `ZoneIntrusionMonitor` para confirmar intrusos con debounce. La
alerta es sonora (adaptador) y visual (overlay); se dispara al comenzar la
intrusion y se repite segun `anti_intruder.alert.repeat_seconds`.
"""

import logging
import time
from contextlib import ExitStack
from dataclasses import dataclass

import cv2

from recognizer.adapters.alert_sound import SilentAlert, SystemSoundAlert
from recognizer.adapters.camera_opencv import OpenCVCamera
from recognizer.adapters.overlay_intrusion import draw_intrusion_overlay
from recognizer.adapters.ultralytics_detector import UltralyticsDetector
from recognizer.bootstrap import resolve_camera_config
from recognizer.cli.console import log_step
from recognizer.cli.paths import prepare_workspace
from recognizer.cli.runtime import RuntimeCallbacks, run_camera_loop
from recognizer.core.config import IntrusionAlertConfig
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.domain.intrusion import (
    IntrusionSnapshot,
    IntrusionZone,
    ZoneIntrusionMonitor,
)
from recognizer.core.errors import RecognizerError
from recognizer.core.pipeline.builder import PipelineBuilder
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.ports.alert_sink import AlertSink
from recognizer.core.ports.object_tracker import ObjectTracker
from recognizer.settings import load_config

LOGGER = logging.getLogger("recognizer.anti_intruder")

WINDOW_NAME = "Anti-intrusos"


@dataclass
class _MonitorState:
    """Estado mutable compartido por los callbacks del bucle de camara."""

    intruders: int = 0
    intruder_ids: tuple[int, ...] = ()
    alerting: bool = False
    last_notified: float = 0.0


def _apply_alert(
    *,
    snapshot: IntrusionSnapshot,
    alert: AlertSink,
    config: IntrusionAlertConfig,
    state: _MonitorState,
    now: float,
) -> None:
    """Dispara la alerta al iniciar la intrusion y la repite mientras dure."""
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


def run_anti_intruder(request: AppRunRequest) -> int:
    """Ejecuta el anti-intrusos.

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
            intruder_config = app_config.anti_intruder
        zone_config = intruder_config.zone
        zone_obj = (
            IntrusionZone(
                x_min=zone_config.x_min,
                y_min=zone_config.y_min,
                x_max=zone_config.x_max,
                y_max=zone_config.y_max,
            )
            if zone_config.enabled
            else None
        )
        monitor = (
            ZoneIntrusionMonitor(
                zone=zone_obj,
                confirm_frames=zone_config.confirm_frames,
                release_frames=zone_config.release_frames,
            )
            if zone_obj is not None
            else None
        )
        pipeline = PipelineBuilder().build()
        detector = UltralyticsDetector(intruder_config)
        tracker: ObjectTracker = detector
        alert = SystemSoundAlert() if intruder_config.alert.enabled else SilentAlert()
        state = _MonitorState()

        def _on_context(context: FrameContext) -> None:
            tracked = tracker.track(context.frame)
            people = tuple(item for item in tracked if item.label == intruder_config.target_label)
            if monitor is not None:
                snapshot = monitor.update(people)
                state.intruders = snapshot.count
                state.intruder_ids = snapshot.intruder_ids
                _apply_alert(
                    snapshot=snapshot,
                    alert=alert,
                    config=intruder_config.alert,
                    state=state,
                    now=time.monotonic(),
                )
            draw_intrusion_overlay(
                context.frame.data,
                tracked=people,
                zone=zone_obj,
                active=state.alerting,
                intruder_ids=frozenset(state.intruder_ids),
            )

        def _on_progress(count: int, fps: float) -> None:
            LOGGER.info(
                "Fotogramas: %d | FPS medio: %.1f | Intrusos: %d | Alerta: %s",
                count,
                fps,
                state.intruders,
                "si" if state.alerting else "no",
            )

        with ExitStack() as stack:
            with log_step(LOGGER, f"Abriendo camara (device={camera_config.device_index})"):
                camera = stack.enter_context(OpenCVCamera(camera_config))
            with log_step(LOGGER, f"Cargando modelo YOLO ({intruder_config.model_path})"):
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
        LOGGER.exception("Error inesperado en el anti-intrusos")
        return 1
    finally:
        alert.close()
        if show_window:
            cv2.destroyAllWindows()

    LOGGER.info(
        "App OK: %d fotogramas, %.1f FPS medio, intrusos finales: %d.",
        frames,
        fps,
        state.intruders,
    )
    return 0
