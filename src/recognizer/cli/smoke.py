"""Prueba de humo de la camara local.

Uso:
    uv run smoke --frames 30 --no-window   # mide FPS y sale
    uv run smoke                           # ventana en vivo (ESC o q para salir)
"""

import argparse
import logging
import sys
import time
from collections.abc import Sequence
from pathlib import Path

import cv2

from recognizer.adapters.camera_opencv import OpenCVCamera
from recognizer.core.config import CameraConfig
from recognizer.core.constants import (
    ESC_KEY,
    FPS_LOG_INTERVAL,
    MAX_CONSECUTIVE_READ_FAILURES,
    MIN_ELAPSED_SECONDS,
)
from recognizer.core.errors import CameraError, RecognizerError
from recognizer.settings import load_config

LOGGER = logging.getLogger("recognizer.smoke")

DEFAULT_CONFIG_PATH = Path("config.yaml")
QUIT_KEY = ord("q")
WINDOW_NAME = "Recognizer - smoke"


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
    return parser


def _resolve_camera_config(config_path: Path, device_override: int | None) -> CameraConfig:
    app_config = load_config(config_path)
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


def _run(camera: OpenCVCamera, *, show_window: bool, max_frames: int) -> tuple[int, float]:
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
        count += 1

        if show_window:
            cv2.imshow(WINDOW_NAME, frame.data)
            pressed = cv2.waitKey(1) & 0xFF
            if pressed in (ESC_KEY, QUIT_KEY):
                break

        if count % FPS_LOG_INTERVAL == 0:
            elapsed = time.perf_counter() - start
            LOGGER.info("Fotogramas: %d | FPS medio: %.1f", count, count / elapsed)

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
        camera_config = _resolve_camera_config(args.config, args.device)
        with OpenCVCamera(camera_config) as camera:
            frames, fps = _run(camera, show_window=show_window, max_frames=args.frames)
    except RecognizerError as exc:
        if show_window:
            cv2.destroyAllWindows()
        LOGGER.error("Smoke fallo: %s", exc)
        return 1
    finally:
        if show_window:
            cv2.destroyAllWindows()

    LOGGER.info("Smoke OK: %d fotogramas, %.1f FPS medio.", frames, fps)
    return 0


if __name__ == "__main__":
    sys.exit(main())
