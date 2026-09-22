"""App Detector de caidas: detecta caidas por pose y dispara alerta.

Usa una sola via de inferencia (modelo YOLO pose) y el dominio puro
``FallDetector`` para confirmar la caida con debounce. El aviso es visual
(overlay) y opcionalmente sonoro; se repite segun
``fall_detector.alert.repeat_seconds``.
"""

import logging
import time
from contextlib import ExitStack
from dataclasses import dataclass

import cv2

from recognizer.adapters.alert_sound import SilentAlert, SystemSoundAlert
from recognizer.adapters.camera_opencv import OpenCVCamera
from recognizer.adapters.overlay_fall import draw_fall_overlay
from recognizer.adapters.ultralytics_pose import UltralyticsPoseEstimator
from recognizer.bootstrap import resolve_camera_config
from recognizer.cli.console import log_step
from recognizer.cli.paths import prepare_workspace
from recognizer.cli.runtime import RuntimeCallbacks, run_camera_loop
from recognizer.core.config import FallDetectorAlertConfig
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.domain.fall import FallDetector, FallSnapshot
from recognizer.core.errors import RecognizerError
from recognizer.core.pipeline.builder import PipelineBuilder
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.ports.alert_sink import AlertSink
from recognizer.settings import load_config

LOGGER = logging.getLogger("recognizer.fall_detector")

WINDOW_NAME = "Detector de caidas"


@dataclass
class _FallState:
    """Estado mutable compartido por los callbacks del bucle de camara."""

    fallen: tuple[int, ...] = ()
    people: int = 0
    active: bool = False
    last_notified: float = 0.0


def _apply_alert(
    *,
    snapshot: FallSnapshot,
    alert: AlertSink,
    config: FallDetectorAlertConfig,
    state: _FallState,
    now: float,
) -> None:
    """Dispara la alerta al confirmar la caida y la repite mientras dure."""
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


def run_fall_detector(request: AppRunRequest) -> int:
    """Ejecuta la app de deteccion de caidas.

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
            fall_config = app_config.fall_detector
        detector = FallDetector(
            min_keypoint_confidence=fall_config.min_keypoint_confidence,
            max_aspect_ratio=fall_config.max_aspect_ratio,
            min_center_y=fall_config.min_center_y,
            max_stillness=fall_config.max_stillness,
            stillness_window=fall_config.stillness_window,
            confirm_frames=fall_config.confirm_frames,
            release_frames=fall_config.release_frames,
        )
        pipeline = PipelineBuilder().build()
        estimator = UltralyticsPoseEstimator(fall_config)
        alert = SystemSoundAlert() if fall_config.alert.enabled else SilentAlert()
        state = _FallState()

        def _on_context(context: FrameContext) -> None:
            poses = estimator.estimate(context.frame)
            snapshot = detector.update(poses)
            state.fallen = snapshot.fallen
            state.people = snapshot.people
            _apply_alert(
                snapshot=snapshot,
                alert=alert,
                config=fall_config.alert,
                state=state,
                now=time.monotonic(),
            )
            draw_fall_overlay(
                context.frame.data,
                poses=poses,
                active=state.active,
                fallen=state.fallen,
                min_keypoint_confidence=fall_config.min_keypoint_confidence,
            )

        def _on_progress(count: int, fps: float) -> None:
            LOGGER.info(
                "Fotogramas: %d | FPS medio: %.1f | Personas: %d | Caidas: %d | Alerta: %s",
                count,
                fps,
                state.people,
                len(state.fallen),
                "si" if state.active else "no",
            )

        with ExitStack() as stack:
            with log_step(LOGGER, f"Abriendo camara (device={camera_config.device_index})"):
                camera = stack.enter_context(OpenCVCamera(camera_config))
            with log_step(LOGGER, f"Cargando modelo YOLO pose ({fall_config.model_path})"):
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
        LOGGER.exception("Error inesperado en la app de detector de caidas")
        return 1
    finally:
        alert.close()
        if show_window:
            cv2.destroyAllWindows()

    LOGGER.info(
        "App OK: %d fotogramas, %.1f FPS medio, caida detectada: %s.",
        frames,
        fps,
        "si" if state.active else "no",
    )
    return 0
