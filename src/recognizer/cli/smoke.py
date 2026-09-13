"""Prueba de humo de camara, manos y overlay.

Uso:
    uv run smoke --frames 30 --no-window   # mide FPS y sale
    uv run smoke --no-hands                # ventana en vivo sin deteccion
    uv run smoke                           # ventana en vivo con manos (ESC o q para salir)
"""

import argparse
import logging
import sys
import time
from collections.abc import Sequence
from contextlib import ExitStack
from pathlib import Path

import cv2

from recognizer.adapters.camera_opencv import OpenCVCamera
from recognizer.adapters.mediapipe_hand_tracker import MediaPipeHandTracker
from recognizer.adapters.overlay_opencv import LandmarkOverlay
from recognizer.core.bus import InProcessEventBus
from recognizer.core.config import AppConfig, CameraConfig
from recognizer.core.constants import (
    ESC_KEY,
    FPS_LOG_INTERVAL,
    MAX_CONSECUTIVE_READ_FAILURES,
    MIN_ELAPSED_SECONDS,
)
from recognizer.core.domain.events import DomainEvent, HandsDetected
from recognizer.core.errors import CameraError, RecognizerError
from recognizer.core.pipeline.builder import Pipeline, PipelineBuilder
from recognizer.core.pipeline.hand_detection import HandDetectionProcessor
from recognizer.core.ports.event_bus import EventBus
from recognizer.core.ports.hand_tracker import HandTracker
from recognizer.settings import load_config

LOGGER = logging.getLogger("recognizer.smoke")

DEFAULT_CONFIG_PATH = Path("config.yaml")
QUIT_KEY = ord("q")
WINDOW_NAME = "Recognizer - smoke"


class _HandsCounter:
    """Cuenta eventos HandsDetected y el maximo de manos visto."""

    def __init__(self) -> None:
        self.events = 0
        self.max_hands = 0

    def handle(self, event: DomainEvent) -> None:
        """Actualiza los contadores segun el tipo de evento."""
        match event:
            case HandsDetected(hands=hands):
                self.events += 1
                self.max_hands = max(self.max_hands, len(hands))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="smoke",
        description="Abre la camara, mide FPS y opcionalmente muestra la imagen.",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--device", type=int, default=None, help="Sobrescribe device_index.")
    parser.add_argument(
        "--frames",
        type=int,
        default=0,
        help="Numero de fotogramas antes de salir (0 = hasta ESC/q en modo ventana).",
    )
    parser.add_argument("--no-window", action="store_true", help="No abre ventana (modo check).")
    parser.add_argument(
        "--no-hands",
        action="store_true",
        help="Desactiva la deteccion de manos y el overlay.",
    )
    return parser


def _resolve_camera_config(app_config: AppConfig, device_override: int | None) -> CameraConfig:
    if device_override is None:
        return app_config.camera
    if device_override < 0:
        msg = "--device debe ser mayor o igual a 0."
        raise RecognizerError(msg)
    return CameraConfig(
        device_index=device_override,
        width=app_config.camera.width,
        height=app_config.camera.height,
        target_fps=app_config.camera.target_fps,
    )


def _build_pipeline(*, tracker: HandTracker | None, bus: EventBus) -> Pipeline:
    builder = PipelineBuilder()
    if tracker is not None:
        builder.add(HandDetectionProcessor(tracker=tracker, bus=bus)).add(LandmarkOverlay())
    return builder.build()


def _run(
    camera: OpenCVCamera,
    *,
    pipeline: Pipeline,
    counter: _HandsCounter,
    show_window: bool,
    max_frames: int,
) -> tuple[int, float]:
    start = time.perf_counter()
    count = 0
    consecutive_failures = 0

    while True:
        frame = camera.read()
        if frame is None:
            consecutive_failures += 1
            if consecutive_failures >= MAX_CONSECUTIVE_READ_FAILURES:
                msg = "La camara dejo de entregar fotogramas."
                raise CameraError(msg)
            continue
        consecutive_failures = 0

        context = pipeline.run(frame)
        count += 1

        if show_window:
            cv2.imshow(WINDOW_NAME, context.frame.data)
            pressed = cv2.waitKey(1) & 0xFF
            if pressed in (ESC_KEY, QUIT_KEY):
                break

        if count % FPS_LOG_INTERVAL == 0:
            elapsed = time.perf_counter() - start
            LOGGER.info(
                "Fotogramas: %d | FPS medio: %.1f | Manos max: %d",
                count,
                count / elapsed,
                counter.max_hands,
            )

        if max_frames > 0 and count >= max_frames:
            break

    elapsed = max(time.perf_counter() - start, MIN_ELAPSED_SECONDS)
    return count, count / elapsed


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del comando `smoke`."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _build_parser().parse_args(argv)
    show_window = not args.no_window

    try:
        if not show_window and args.frames <= 0:
            msg = "Sin ventana no hay ESC: usa --frames > 0 junto con --no-window."
            raise RecognizerError(msg)
        app_config = load_config(args.config)
        camera_config = _resolve_camera_config(app_config, args.device)
        bus = InProcessEventBus()
        counter = _HandsCounter()
        bus.subscribe(HandsDetected, counter.handle)
        tracker = None if args.no_hands else MediaPipeHandTracker(app_config.hands)
        pipeline = _build_pipeline(tracker=tracker, bus=bus)

        with ExitStack() as stack:
            camera = stack.enter_context(OpenCVCamera(camera_config))
            if tracker is not None:
                stack.enter_context(tracker)
            frames, fps = _run(
                camera,
                pipeline=pipeline,
                counter=counter,
                show_window=show_window,
                max_frames=args.frames,
            )
    except RecognizerError as exc:
        LOGGER.error("Smoke fallo: %s", exc)
        return 1
    finally:
        if show_window:
            cv2.destroyAllWindows()

    LOGGER.info(
        "Smoke OK: %d fotogramas, %.1f FPS medio, maximo de manos: %d (eventos: %d).",
        frames,
        fps,
        counter.max_hands,
        counter.events,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
