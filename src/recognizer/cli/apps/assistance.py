"""App Manos arriba / asistencia: detecta brazos levantados y pide ayuda.

Usa una sola via de inferencia (modelo YOLO pose) y el dominio puro
`AssistanceMonitor` para confirmar el pedido con debounce. El aviso es visual
(overlay) y opcionalmente sonoro; se repite segun
`assistance.alert.repeat_seconds`.
"""

import logging
import time
from contextlib import ExitStack
from dataclasses import dataclass

import cv2

from recognizer.adapters.alert_sound import SilentAlert, SystemSoundAlert
from recognizer.adapters.camera_opencv import OpenCVCamera
from recognizer.adapters.overlay_assistance import draw_assistance_overlay
from recognizer.adapters.ultralytics_pose import UltralyticsPoseEstimator
from recognizer.bootstrap import resolve_camera_config
from recognizer.cli.console import log_step
from recognizer.cli.paths import prepare_workspace
from recognizer.cli.runtime import RuntimeCallbacks, run_camera_loop
from recognizer.core.config import AssistanceAlertConfig
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.domain.assistance import AssistanceMonitor, AssistanceSnapshot
from recognizer.core.errors import RecognizerError
from recognizer.core.pipeline.builder import PipelineBuilder
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.ports.alert_sink import AlertSink
from recognizer.settings import load_config

LOGGER = logging.getLogger("recognizer.assistance")

WINDOW_NAME = "Manos arriba / asistencia"


@dataclass
class _AssistanceState:
    """Estado mutable compartido por los callbacks del bucle de camara."""

    raised: tuple[int, ...] = ()
    people: int = 0
    active: bool = False
    last_notified: float = 0.0


def _apply_alert(
    *,
    snapshot: AssistanceSnapshot,
    alert: AlertSink,
    config: AssistanceAlertConfig,
    state: _AssistanceState,
    now: float,
) -> None:
    """Dispara la alerta al confirmar el pedido y la repite mientras dure."""
    if not snapshot.active:
        state.active = False
        return
    if not state.active:
        state.active = True
        state.last_notified = now
        alert.notify()
        return
    if config.repeat_seconds > 0 and now - state.last_notified >= config.repeat_seconds:
        state.last_notified = now
        alert.notify()


def run_assistance(request: AppRunRequest) -> int:
    """Ejecuta la app de asistencia por brazos levantados.

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
            assistance_config = app_config.assistance
        monitor = AssistanceMonitor(
            min_keypoint_confidence=assistance_config.min_keypoint_confidence,
            raise_margin=assistance_config.raise_margin,
            required_arms=assistance_config.required_arms,
            confirm_frames=assistance_config.confirm_frames,
            release_frames=assistance_config.release_frames,
        )
        pipeline = PipelineBuilder().build()
        estimator = UltralyticsPoseEstimator(assistance_config)
        alert = SystemSoundAlert() if assistance_config.alert.enabled else SilentAlert()
        state = _AssistanceState()

        def _on_context(context: FrameContext) -> None:
            poses = estimator.estimate(context.frame)
            snapshot = monitor.update(poses)
            state.raised = snapshot.raised
            state.people = snapshot.people
            _apply_alert(
                snapshot=snapshot,
                alert=alert,
                config=assistance_config.alert,
                state=state,
                now=time.monotonic(),
            )
            draw_assistance_overlay(
                context.frame.data,
                poses=poses,
                active=state.active,
                raised=state.raised,
                min_keypoint_confidence=assistance_config.min_keypoint_confidence,
                raise_margin=assistance_config.raise_margin,
            )

        def _on_progress(count: int, fps: float) -> None:
            LOGGER.info(
                "Fotogramas: %d | FPS medio: %.1f | Personas: %d | Brazos arriba: %d | Alerta: %s",
                count,
                fps,
                state.people,
                len(state.raised),
                "si" if state.active else "no",
            )

        with ExitStack() as stack:
            with log_step(LOGGER, f"Abriendo camara (device={camera_config.device_index})"):
                camera = stack.enter_context(OpenCVCamera(camera_config))
            with log_step(LOGGER, f"Cargando modelo YOLO pose ({assistance_config.model_path})"):
                stack.enter_context(estimator)
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
        LOGGER.exception("Error inesperado en la app de asistencia")
        return 1
    finally:
        alert.close()
        if show_window:
            cv2.destroyAllWindows()

    LOGGER.info(
        "App OK: %d fotogramas, %.1f FPS medio, alerta de asistencia: %s.",
        frames,
        fps,
        "si" if state.active else "no",
    )
    return 0
