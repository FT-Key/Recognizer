"""Bucle de camara compartido por smoke y la app local."""

import contextlib
import time
from collections.abc import Callable
from dataclasses import dataclass

import cv2

from recognizer.core.constants import (
    ESC_KEY,
    FPS_LOG_INTERVAL,
    MAX_CONSECUTIVE_READ_FAILURES,
    MIN_ELAPSED_SECONDS,
    WINDOW_MIN_VISIBLE_VALUE,
    WINDOW_TOPMOST_DISABLED,
    WINDOW_TOPMOST_ENABLED,
)
from recognizer.core.errors import CameraError
from recognizer.core.pipeline.builder import Pipeline
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.ports.frame_source import FrameSource

QUIT_KEY = ord("q")


@dataclass(frozen=True, slots=True)
class RuntimeCallbacks:
    """Callbacks opcionales del bucle; todos son no-op por defecto."""

    on_key: Callable[[int], None] | None = None
    on_context: Callable[[FrameContext], None] | None = None
    on_progress: Callable[[int, float], None] | None = None


DEFAULT_CALLBACKS = RuntimeCallbacks()


def _bring_to_front(*, window_name: str) -> None:
    """Crea la ventana y la trae al frente; ignora backends sin soporte topmost."""
    with contextlib.suppress(cv2.error):
        cv2.namedWindow(window_name)
        cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, WINDOW_TOPMOST_ENABLED)
        cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, WINDOW_TOPMOST_DISABLED)


def _window_closed(*, window_name: str) -> bool:
    """Indica si la ventana se cerro con la X; False si el backend no lo soporta."""
    try:
        visible = cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE)
    except cv2.error:
        return False
    return bool(visible < WINDOW_MIN_VISIBLE_VALUE)


def run_camera_loop(
    camera: FrameSource,
    *,
    pipeline: Pipeline,
    window_name: str,
    show_window: bool,
    max_frames: int,
    callbacks: RuntimeCallbacks = DEFAULT_CALLBACKS,
) -> tuple[int, float]:
    """Lee de la camara, ejecuta el pipeline y maneja ventana y corte.

    Returns:
        Tupla con el numero de fotogramas procesados y los FPS medios.

    Raises:
        CameraError: si la camara deja de entregar fotogramas.
    """
    start = time.perf_counter()
    count = 0
    consecutive_failures = 0

    if show_window:
        _bring_to_front(window_name=window_name)

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
        if callbacks.on_context is not None:
            callbacks.on_context(context)
        count += 1

        if show_window:
            cv2.imshow(window_name, context.frame.data)
            pressed = cv2.waitKey(1) & 0xFF
            if callbacks.on_key is not None:
                callbacks.on_key(pressed)
            if pressed in (ESC_KEY, QUIT_KEY):
                break
            if _window_closed(window_name=window_name):
                break

        if count % FPS_LOG_INTERVAL == 0:
            elapsed = time.perf_counter() - start
            if callbacks.on_progress is not None:
                callbacks.on_progress(count, count / elapsed)

        if max_frames > 0 and count >= max_frames:
            break

    elapsed = max(time.perf_counter() - start, MIN_ELAPSED_SECONDS)
    return count, count / elapsed
