"""App Postura ergonomica: estima pose con YOLO y avisa de malos habitos.

Usa una sola via de inferencia (`model.predict` de un modelo pose) y el dominio
puro `PostureMonitor` para confirmar la mala postura con debounce. El aviso es
visual (overlay) y opcionalmente sonoro; se repite segun `posture.alert.repeat_seconds`.
"""

import logging
import time
from contextlib import ExitStack
from dataclasses import dataclass

import cv2

from recognizer.adapters.alert_sound import SilentAlert, SystemSoundAlert
from recognizer.adapters.camera_opencv import OpenCVCamera
from recognizer.adapters.overlay_posture import draw_posture_overlay
from recognizer.adapters.ultralytics_pose import UltralyticsPoseEstimator
from recognizer.bootstrap import resolve_camera_config
from recognizer.cli.console import log_step
from recognizer.cli.paths import prepare_workspace
from recognizer.cli.runtime import RuntimeCallbacks, run_camera_loop
from recognizer.core.config import PostureAlertConfig
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.domain.posture import (
    PostureMonitor,
    PostureSnapshot,
    PostureThresholds,
    PostureTolerances,
)
from recognizer.core.errors import RecognizerError
from recognizer.core.pipeline.builder import PipelineBuilder
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.ports.alert_sink import AlertSink
from recognizer.settings import load_config

LOGGER = logging.getLogger("recognizer.posture")

WINDOW_NAME = "Postura ergonomica"


@dataclass
class _PostureState:
    """Estado mutable compartido por los callbacks del bucle de camara."""

    issues: tuple[str, ...] = ()
    active: bool = False
    calibrating: bool = False
    last_notified: float = 0.0


def _apply_alert(
    *,
    snapshot: PostureSnapshot,
    alert: AlertSink,
    config: PostureAlertConfig,
    state: _PostureState,
    now: float,
) -> None:
    """Dispara la alerta al confirmar mala postura y la repite mientras dure."""
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


def run_posture(request: AppRunRequest) -> int:
    """Ejecuta la app de postura ergonomica.

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
            posture_config = app_config.posture
        thresholds = PostureThresholds(
            max_head_offset_ratio=posture_config.max_head_offset_ratio,
            min_head_height_ratio=posture_config.min_head_height_ratio,
            max_torso_angle_deg=posture_config.max_torso_angle_deg,
            max_shoulder_tilt_ratio=posture_config.max_shoulder_tilt_ratio,
        )
        tolerances = PostureTolerances(
            head_offset=posture_config.tolerances.head_offset,
            head_height=posture_config.tolerances.head_height,
            torso_angle_deg=posture_config.tolerances.torso_angle_deg,
            shoulder_tilt=posture_config.tolerances.shoulder_tilt,
        )
        monitor = PostureMonitor(
            thresholds=thresholds,
            min_keypoint_confidence=posture_config.min_keypoint_confidence,
            confirm_frames=posture_config.confirm_frames,
            release_frames=posture_config.release_frames,
            calibration_frames=posture_config.calibration_frames,
            tolerances=tolerances,
        )
        pipeline = PipelineBuilder().build()
        estimator = UltralyticsPoseEstimator(posture_config)
        alert = SystemSoundAlert() if posture_config.alert.enabled else SilentAlert()
        state = _PostureState()

        def _on_context(context: FrameContext) -> None:
            poses = estimator.estimate(context.frame)
            snapshot = monitor.update(poses)
            state.calibrating = snapshot.calibrating
            if snapshot.calibrating:
                state.active = False
                state.issues = ()
            else:
                state.issues = tuple(issue.value for issue in snapshot.issues)
                _apply_alert(
                    snapshot=snapshot,
                    alert=alert,
                    config=posture_config.alert,
                    state=state,
                    now=time.monotonic(),
                )
            draw_posture_overlay(
                context.frame.data,
                poses=poses,
                active=state.active,
                issues=snapshot.issues,
                min_keypoint_confidence=posture_config.min_keypoint_confidence,
                calibrating=state.calibrating,
            )

        def _on_progress(count: int, fps: float) -> None:
            if state.calibrating:
                LOGGER.info(
                    "Fotogramas: %d | FPS medio: %.1f | Calibrando (sientate derecho)...",
                    count,
                    fps,
                )
                return
            LOGGER.info(
                "Fotogramas: %d | FPS medio: %.1f | Postura: %s | Aviso: %s",
                count,
                fps,
                ", ".join(state.issues) if state.issues else "OK",
                "si" if state.active else "no",
            )

        with ExitStack() as stack:
            with log_step(LOGGER, f"Abriendo camara (device={camera_config.device_index})"):
                camera = stack.enter_context(OpenCVCamera(camera_config))
            with log_step(LOGGER, f"Cargando modelo YOLO pose ({posture_config.model_path})"):
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
        LOGGER.exception("Error inesperado en la app de postura")
        return 1
    finally:
        alert.close()
        if show_window:
            cv2.destroyAllWindows()

    LOGGER.info(
        "App OK: %d fotogramas, %.1f FPS medio, avisos de postura: %s.",
        frames,
        fps,
        "si" if state.active else "no",
    )
    return 0
