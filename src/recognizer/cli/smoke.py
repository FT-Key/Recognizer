"""Prueba de humo de camara, gestos y overlay.

Uso:
    uv run smoke --frames 30 --no-window   # mide FPS y sale
    uv run smoke --no-hands                # ventana en vivo sin deteccion
    uv run smoke                           # ventana en vivo con gestos (ESC o q para salir)
"""

import argparse
import logging
import sys
from collections import Counter
from collections.abc import Sequence
from contextlib import ExitStack
from pathlib import Path

import cv2

from recognizer.adapters.camera_opencv import OpenCVCamera
from recognizer.adapters.mediapipe_gesture_classifier import MediaPipeGestureClassifier
from recognizer.bootstrap import build_pipeline, resolve_camera_config
from recognizer.cli.runtime import RuntimeCallbacks, run_camera_loop
from recognizer.core.bus import InProcessEventBus
from recognizer.core.config import GestureConfig
from recognizer.core.domain.events import (
    DomainEvent,
    GestureDetected,
    GestureReleased,
    HandsDetected,
)
from recognizer.core.domain.gesture import GestureName
from recognizer.core.errors import RecognizerError
from recognizer.core.pipeline.builder import Pipeline
from recognizer.core.ports.event_bus import EventBus
from recognizer.core.ports.gesture_classifier import GestureClassifier
from recognizer.settings import load_config

LOGGER = logging.getLogger("recognizer.smoke")

DEFAULT_CONFIG_PATH = Path("config.yaml")
WINDOW_NAME = "Recognizer - smoke"
NO_CONFIRMED_GESTURES = "ninguno"


class _GestureStats:
    """Cuenta eventos de manos y gestos confirmados publicados al bus."""

    def __init__(self) -> None:
        self.hands_events = 0
        self.max_hands = 0
        self.detected_events = 0
        self.released_events = 0
        self.confirmed: Counter[GestureName] = Counter()

    def handle(self, event: DomainEvent) -> None:
        """Actualiza los contadores segun el tipo de evento."""
        match event:
            case HandsDetected(hands=hands):
                self.hands_events += 1
                self.max_hands = max(self.max_hands, len(hands))
            case GestureDetected(gesture=gesture):
                self.detected_events += 1
                self.confirmed[gesture] += 1
            case GestureReleased():
                self.released_events += 1


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
        help="Desactiva la deteccion de manos/gestos y el overlay.",
    )
    return parser


def _build_pipeline(
    *,
    classifier: GestureClassifier | None,
    bus: EventBus,
    gestures: GestureConfig,
) -> Pipeline:
    return build_pipeline(classifier=classifier, bus=bus, gestures=gestures)


def _format_confirmed(confirmed: Counter[GestureName]) -> str:
    if not confirmed:
        return NO_CONFIRMED_GESTURES
    return ", ".join(f"{name.value}={count}" for name, count in confirmed.items())


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
        camera_config = resolve_camera_config(app_config=app_config, device_override=args.device)
        bus = InProcessEventBus()
        stats = _GestureStats()
        bus.subscribe(HandsDetected, stats.handle)
        bus.subscribe(GestureDetected, stats.handle)
        bus.subscribe(GestureReleased, stats.handle)
        classifier = None if args.no_hands else MediaPipeGestureClassifier(app_config.gestures)
        pipeline = _build_pipeline(classifier=classifier, bus=bus, gestures=app_config.gestures)

        def _log_progress(count: int, fps: float) -> None:
            LOGGER.info(
                "Fotogramas: %d | FPS medio: %.1f | Manos max: %d | Gestos confirmados: %d",
                count,
                fps,
                stats.max_hands,
                stats.detected_events,
            )

        with ExitStack() as stack:
            camera = stack.enter_context(OpenCVCamera(camera_config))
            if classifier is not None:
                stack.enter_context(classifier)
            frames, fps = run_camera_loop(
                camera,
                pipeline=pipeline,
                window_name=WINDOW_NAME,
                show_window=show_window,
                max_frames=args.frames,
                callbacks=RuntimeCallbacks(on_progress=_log_progress),
            )
    except RecognizerError as exc:
        LOGGER.error("Smoke fallo: %s", exc)
        return 1
    finally:
        if show_window:
            cv2.destroyAllWindows()

    LOGGER.info(
        "Smoke OK: %d fotogramas, %.1f FPS medio, maximo de manos: %d, gestos confirmados: %s "
        "(HandsDetected: %d, GestureDetected: %d, GestureReleased: %d).",
        frames,
        fps,
        stats.max_hands,
        _format_confirmed(stats.confirmed),
        stats.hands_events,
        stats.detected_events,
        stats.released_events,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
