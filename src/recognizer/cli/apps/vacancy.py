"""App Vacancy: detecta ausencia de personas en la camara.

Usa una sola via de inferencia (`model.track`, que incluye la deteccion) y el
dominio puro `VacancyMonitor` para detectar cuando no hay personas visibles
durante mas de N segundos. Util para museos, galerias o salas que requieren
al menos una persona presente.
"""

import logging
import time
from contextlib import ExitStack
from dataclasses import dataclass

import cv2

from recognizer.adapters.alert_sound import SilentAlert, SystemSoundAlert
from recognizer.adapters.camera_opencv import OpenCVCamera
from recognizer.adapters.overlay_vacancy import draw_vacancy_overlay
from recognizer.adapters.ultralytics_detector import UltralyticsDetector
from recognizer.bootstrap import resolve_camera_config
from recognizer.cli.console import log_step
from recognizer.cli.paths import prepare_workspace
from recognizer.cli.runtime import RuntimeCallbacks, run_camera_loop
from recognizer.core.config import VacancyAlertConfig
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.domain.vacancy import VacancyMonitor, VacancySnapshot
from recognizer.core.errors import RecognizerError
from recognizer.core.pipeline.builder import PipelineBuilder
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.ports.alert_sink import AlertSink
from recognizer.core.ports.object_tracker import ObjectTracker
from recognizer.settings import load_config

LOGGER = logging.getLogger("recognizer.vacancy")

WINDOW_NAME = "Zona vacia"


@dataclass
class _MonitorState:
    """Estado mutable compartido por los callbacks del bucle de camara."""

    people_count: int = 0
    alerting: bool = False
    last_notified: float = 0.0
    empty_seconds: float = 0.0


def _apply_alert(
    *,
    snapshot: VacancySnapshot,
    alert: AlertSink,
    config: VacancyAlertConfig,
    state: _MonitorState,
    now: float,
) -> None:
    """Dispara la alerta al detectar ausencia y la repite mientras dure."""
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


def run_vacancy(request: AppRunRequest) -> int:
    """Ejecuta la app de zona vacia.

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
            vacancy_config = app_config.vacancy
        monitor = VacancyMonitor(
            confirm_frames=vacancy_config.confirm_frames,
            release_frames=vacancy_config.release_frames,
        )
        pipeline = PipelineBuilder().build()
        detector = UltralyticsDetector(vacancy_config)
        tracker: ObjectTracker = detector
        alert = SystemSoundAlert() if vacancy_config.alert.enabled else SilentAlert()
        state = _MonitorState()

        def _on_context(context: FrameContext) -> None:
            tracked = tracker.track(context.frame)
            people = tuple(item for item in tracked if item.label == vacancy_config.target_label)
            snapshot = monitor.update(people)
            state.people_count = snapshot.people_count
            state.alerting = snapshot.active
            _apply_alert(
                snapshot=snapshot,
                alert=alert,
                config=vacancy_config.alert,
                state=state,
                now=time.monotonic(),
            )
            draw_vacancy_overlay(
                context.frame.data,
                people_count=state.people_count,
                active=state.alerting,
                empty_seconds=state.empty_seconds,
            )

        def _on_progress(count: int, fps: float) -> None:
            LOGGER.info(
                "Fotogramas: %d | FPS medio: %.1f | Personas: %d | Ausencia: %s",
                count,
                fps,
                state.people_count,
                "si" if state.alerting else "no",
            )

        with ExitStack() as stack:
            with log_step(LOGGER, f"Abriendo camara (device={camera_config.device_index})"):
                camera = stack.enter_context(OpenCVCamera(camera_config))
            with log_step(LOGGER, f"Cargando modelo YOLO ({vacancy_config.model_path})"):
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
        LOGGER.exception("Error inesperado en la zona vacia")
        return 1
    finally:
        alert.close()
        if show_window:
            cv2.destroyAllWindows()

    LOGGER.info(
        "App OK: %d fotogramas, %.1f FPS medio, personas finales: %d.",
        frames,
        fps,
        state.people_count,
    )
    return 0
