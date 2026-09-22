"""App Somnolencia: detecta somnolencia con pose + face mesh (EAR/MAR).

Usa dos vias de inferencia: YOLO pose (cabeza caida, cabeceo) y MediaPipe
Face Mesh (EAR ojos cerrados, MAR bostezo). La inferencia corre en un worker
(`LatestFrameSource`) y el bucle principal solo dibuja; asi la camara de red
(telofono) no acumula retraso. El dominio puro ``DrowsinessDetector`` combina
ambas senales y confirma la somnolencia con debounce. El aviso es visual
(overlay) y opcionalmente sonoro; se repite segun
``drowsiness.alert.repeat_seconds``.
"""

import logging
import time
from contextlib import ExitStack
from dataclasses import dataclass, field

import cv2

from recognizer.adapters.alert_sound import SilentAlert, SystemSoundAlert
from recognizer.adapters.camera_opencv import OpenCVCamera
from recognizer.adapters.latest_frame_source import LatestFrameSource
from recognizer.adapters.mediapipe_face_mesh import MediaPipeFaceMesh
from recognizer.adapters.overlay_drowsiness import draw_drowsiness_overlay
from recognizer.adapters.ultralytics_pose import UltralyticsPoseEstimator
from recognizer.bootstrap import resolve_camera_config
from recognizer.cli.console import log_step
from recognizer.cli.inference_worker import LatestInferenceWorker
from recognizer.cli.paths import prepare_workspace
from recognizer.cli.runtime import RuntimeCallbacks, run_camera_loop
from recognizer.core.config import DrowsinessAlertConfig, DrowsinessConfig
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.domain.drowsiness import DrowsinessDetector, DrowsinessSnapshot
from recognizer.core.domain.face_landmarks import FaceMeshResult
from recognizer.core.domain.pose import Pose
from recognizer.core.errors import RecognizerError
from recognizer.core.pipeline.builder import PipelineBuilder
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.ports.alert_sink import AlertSink
from recognizer.settings import load_config

LOGGER = logging.getLogger("recognizer.drowsiness")

WINDOW_NAME = "Detector de somnolencia"


@dataclass
class _DrowsinessState:
    """Estado mutable compartido por los callbacks del bucle de camara."""

    drowsy_count: int = 0
    people: int = 0
    active: bool = False
    last_notified: float = 0.0
    poses: tuple[Pose, ...] = field(default_factory=tuple)
    snapshot: DrowsinessSnapshot = field(default_factory=lambda: DrowsinessSnapshot(active=False))


def _apply_alert(
    *,
    snapshot: DrowsinessSnapshot,
    alert: AlertSink,
    config: DrowsinessAlertConfig,
    state: _DrowsinessState,
    now: float,
) -> None:
    """Dispara la alerta al confirmar somnolencia y la repite mientras dure."""
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


def run_drowsiness(request: AppRunRequest) -> int:
    """Ejecuta la app de deteccion de somnolencia.

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
            drowsiness_config = app_config.drowsiness

        detector = DrowsinessDetector(
            min_keypoint_confidence=drowsiness_config.min_keypoint_confidence,
            head_droop_threshold=drowsiness_config.head_droop_threshold,
            nod_amplitude_threshold=drowsiness_config.nod_amplitude_threshold,
            nodding_window=drowsiness_config.nodding_window,
            ear_threshold=drowsiness_config.ear_threshold,
            eye_close_frames=drowsiness_config.eye_close_frames,
            mar_threshold=drowsiness_config.mar_threshold,
            yawn_frames=drowsiness_config.yawn_frames,
            confirm_frames=drowsiness_config.confirm_frames,
            release_frames=drowsiness_config.release_frames,
        )
        pipeline = PipelineBuilder().build()
        pose_estimator = UltralyticsPoseEstimator(drowsiness_config)

        # Face mesh config: reutiliza los campos de DrowsinessConfig
        class _FaceMeshConfig:
            """Adaptador inline para FaceMeshConfig protocol."""

            def __init__(self, dc: DrowsinessConfig) -> None:
                self.model_path = str(dc.face_mesh_model_path)
                self.min_face_detection_confidence = float(dc.face_detection_confidence)
                self.min_face_presence_confidence = float(dc.face_presence_confidence)

        face_mesh = MediaPipeFaceMesh(_FaceMeshConfig(drowsiness_config))

        alert = SystemSoundAlert() if drowsiness_config.alert.enabled else SilentAlert()
        state = _DrowsinessState()

        def _on_result(payload: tuple[tuple[Pose, ...], tuple[FaceMeshResult, ...]]) -> None:
            poses, faces = payload
            snapshot = detector.update(poses, faces)
            state.poses = poses
            state.snapshot = snapshot
            state.drowsy_count = snapshot.drowsy_count
            state.people = snapshot.people
            _apply_alert(
                snapshot=snapshot,
                alert=alert,
                config=drowsiness_config.alert,
                state=state,
                now=time.monotonic(),
            )

        def _on_context(context: FrameContext) -> None:
            if worker.error is not None:
                raise worker.error
            snapshot = state.snapshot
            draw_drowsiness_overlay(
                context.frame.data,
                poses=state.poses,
                active=state.active,
                drowsy_count=state.drowsy_count,
                min_keypoint_confidence=drowsiness_config.min_keypoint_confidence,
                ear_avg=snapshot.ear_avg,
                mar=snapshot.mar,
                head_droop=snapshot.head_droop,
                nod_amplitude=snapshot.nod_amplitude,
            )

        def _on_progress(count: int, fps: float) -> None:
            LOGGER.info(
                "Fotogramas: %d | FPS medio: %.1f | Personas: %d | Somnolientos: %d | Alerta: %s",
                count,
                fps,
                state.people,
                state.drowsy_count,
                "si" if state.active else "no",
            )

        with ExitStack() as stack:
            camera = OpenCVCamera(camera_config)
            with log_step(LOGGER, f"Abriendo camara (device={camera_config.device_index})"):
                # LatestFrameSource abre la camara y arranca el hilo de captura;
                # no se entra la camara aparte (seria una doble apertura).
                source = stack.enter_context(LatestFrameSource(camera))
            with log_step(LOGGER, f"Cargando modelo YOLO pose ({drowsiness_config.model_path})"):
                stack.enter_context(pose_estimator)
            with log_step(
                LOGGER,
                f"Cargando modelo Face Mesh ({drowsiness_config.face_mesh_model_path})",
            ):
                stack.enter_context(face_mesh)
            stack.enter_context(alert)
            worker = stack.enter_context(
                LatestInferenceWorker(
                    source=source,
                    infer=lambda frame: (pose_estimator.estimate(frame), face_mesh.detect(frame)),
                    on_result=_on_result,
                    logger=LOGGER,
                    name="recognizer-drowsiness-infer",
                )
            )
            LOGGER.info("Listo. Pulsa ESC o q para volver al menu.")
            frames, fps = run_camera_loop(
                source,
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
        LOGGER.exception("Error inesperado en la app de somnolencia")
        return 1
    finally:
        alert.close()
        if show_window:
            cv2.destroyAllWindows()

    LOGGER.info(
        "App OK: %d fotogramas, %.1f FPS medio, somnolencia detectada: %s.",
        frames,
        fps,
        "si" if state.active else "no",
    )
    return 0
