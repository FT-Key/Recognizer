"""App OCR en vivo: lee texto/patentes en un ROI con EasyOCR.

El bucle principal solo dibuja; un hilo worker corre EasyOCR sobre el fotograma
mas reciente (``LatestFrameSource``) para que la ventana vaya a ritmo de camara
aunque la inferencia tarde cientos de milisegundos.
"""

import contextlib
import logging
import threading
import time
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass, field

import cv2
import numpy as np

from recognizer.adapters.camera_opencv import OpenCVCamera
from recognizer.adapters.easyocr_engine import EasyOCREngine
from recognizer.adapters.latest_frame_source import LatestFrameSource
from recognizer.adapters.overlay_ocr import draw_ocr_overlay
from recognizer.bootstrap import resolve_camera_config
from recognizer.cli.console import log_step
from recognizer.cli.paths import prepare_workspace
from recognizer.cli.runtime import RuntimeCallbacks, run_camera_loop
from recognizer.core.constants import (
    OCR_SIGNATURE_SIZE,
    OCR_WORKER_JOIN_TIMEOUT_SECONDS,
    OCR_WORKER_WAIT_TIMEOUT_SECONDS,
)
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.ocr import ROI, OCRBox
from recognizer.core.errors import RecognizerError
from recognizer.core.pipeline.builder import PipelineBuilder
from recognizer.core.pipeline.context import FrameContext
from recognizer.settings import load_config

LOGGER = logging.getLogger("recognizer.ocr_reader")

WINDOW_NAME = "OCR en vivo"


@dataclass
class _OCRState:
    """Estado mutable compartido por los callbacks del bucle de camara."""

    boxes: tuple[OCRBox, ...] = ()
    texts: tuple[str, ...] = ()
    roi: ROI = field(default_factory=lambda: ROI(x_min=0.1, y_min=0.1, x_max=0.9, y_max=0.9))


def _opencv_gui_available() -> bool:
    """Verifica si OpenCV tiene soporte de ventana (GUI)."""
    try:
        cv2.namedWindow("__probe__")
        cv2.destroyWindow("__probe__")
        return True
    except cv2.error:
        return False


def _rescale_boxes(boxes: tuple[OCRBox, ...], factor: float) -> tuple[OCRBox, ...]:
    """Reubica las cajas de un fotograma reducido al fotograma original."""
    return tuple(
        OCRBox(
            x_min=round(box.x_min * factor),
            y_min=round(box.y_min * factor),
            x_max=round(box.x_max * factor),
            y_max=round(box.y_max * factor),
            text=box.text,
            confidence=box.confidence,
        )
        for box in boxes
    )


class _OCRWorker:
    """Hilo que corre EasyOCR sobre el fotograma mas reciente sin frenar la captura.

    Toma fotogramas de ``LatestFrameSource`` sin consumirlos (version propia),
    ejecuta OCR cada ``process_every_n_frames`` y como maximo ``max_inference_fps``
    veces por segundo, y entrega las cajas detectadas. El bucle principal solo
    dibuja, asi que la ventana va a ritmo de camara aunque la inferencia tarde.
    """

    def __init__(
        self,
        *,
        source: LatestFrameSource,
        engine: EasyOCREngine,
        roi: ROI,
        process_every_n_frames: int,
        on_result: Callable[[tuple[OCRBox, ...]], None],
        logger: logging.Logger,
        max_inference_fps: float = 0.0,
        change_threshold: float = 0.0,
        max_frame_width: int = 0,
    ) -> None:
        self._source = source
        self._engine = engine
        self._roi = roi
        self._every = max(1, process_every_n_frames)
        self._on_result = on_result
        self._logger = logger
        self._min_interval = 1.0 / max_inference_fps if max_inference_fps > 0 else 0.0
        self._change_threshold = change_threshold
        self._max_frame_width = max_frame_width
        self._last_signature: np.ndarray | None = None
        self._last_inference = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._error: RecognizerError | None = None

    def start(self) -> None:
        """Arranca el hilo de inferencia."""
        self._thread = threading.Thread(target=self._run, name="recognizer-ocr-infer", daemon=True)
        self._thread.start()

    def _downscale(self, frame: Frame) -> tuple[np.ndarray, float]:
        """Reduce el fotograma a ``max_frame_width``; devuelve el array y la escala.

        Las camaras de red (telefono) entregan alta resolucion: reducir antes de
        convertir/detectar abarata el trabajo por fotograma. La escala permite
        reubicar las cajas en el fotograma original para el overlay.
        """
        data = frame.data
        if self._max_frame_width > 0 and data.shape[1] > self._max_frame_width:
            scale = self._max_frame_width / data.shape[1]
            new_height = max(1, round(data.shape[0] * scale))
            data = cv2.resize(  # type: ignore[assignment]
                data, (self._max_frame_width, new_height), interpolation=cv2.INTER_AREA
            )
            return data, scale
        return data, 1.0

    def _signature(self, data: np.ndarray) -> np.ndarray:
        """Firma barata de la ROI (grises 32x32) para detectar cambios."""
        height, width = data.shape[:2]
        x1, y1, x2, y2 = self._roi.pixel_rect(width, height)
        crop = data[y1:y2, x1:x2]
        if crop.size == 0:
            return np.zeros((OCR_SIGNATURE_SIZE, OCR_SIGNATURE_SIZE), dtype=np.uint8)
        small = cv2.resize(
            crop, (OCR_SIGNATURE_SIZE, OCR_SIGNATURE_SIZE), interpolation=cv2.INTER_AREA
        )
        return cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

    def _changed(self, signature: np.ndarray) -> bool:
        """True si la ROI cambio lo suficiente respecto al ultimo fotograma visto."""
        previous = self._last_signature
        self._last_signature = signature
        if previous is None or self._change_threshold <= 0:
            return True
        diff = float(np.mean(np.abs(signature.astype(np.int16) - previous.astype(np.int16))))
        return diff >= self._change_threshold

    def _run(self) -> None:
        version = 0
        seen = 0
        while not self._stop.is_set():
            got = self._source.wait_for_new(version, timeout=OCR_WORKER_WAIT_TIMEOUT_SECONDS)
            if got is None:
                continue
            frame, version = got
            seen += 1
            if seen % self._every != 0:
                continue
            data, scale = self._downscale(frame)
            if not self._changed(self._signature(data)):
                continue
            now = time.monotonic()
            if self._min_interval > 0 and now - self._last_inference < self._min_interval:
                continue
            self._last_inference = now
            height, width = data.shape[:2]
            try:
                image_rgb = cv2.cvtColor(data, cv2.COLOR_BGR2RGB)
                boxes = self._engine.read(
                    image_rgb,  # type: ignore[arg-type]
                    self._roi,
                    frame_width=width,
                    frame_height=height,
                )
                if scale != 1.0:
                    boxes = _rescale_boxes(boxes, 1.0 / scale)
            except Exception as exc:  # el hilo no debe morir en silencio
                error = (
                    exc
                    if isinstance(exc, RecognizerError)
                    else RecognizerError(f"Fallo la inferencia OCR: {exc}")
                )
                self._error = error
                self._logger.error("Fallo la inferencia OCR: %s", exc)
                self._stop.set()
                return
            if self._stop.is_set():
                return
            self._on_result(boxes)

    def stop(self) -> None:
        """Detiene el hilo y espera a que termine."""
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=OCR_WORKER_JOIN_TIMEOUT_SECONDS)
            if thread.is_alive():
                self._logger.warning(
                    "El worker de OCR no termino en %.1fs; se continua el cierre.",
                    OCR_WORKER_JOIN_TIMEOUT_SECONDS,
                )
            self._thread = None

    @property
    def error(self) -> RecognizerError | None:
        """Error de inferencia capturado en el worker, si lo hubo."""
        return self._error

    def __enter__(self) -> "_OCRWorker":
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stop()


def run_ocr_reader(request: AppRunRequest) -> int:
    """Ejecuta la app de OCR en vivo.

    Pensada para el launcher: al salir (ESC/q) devuelve el control al llamador
    en lugar de terminar el proceso. Devuelve 0 si termino bien, 1 si fallo.
    """
    show_window = request.show_window and _opencv_gui_available()
    max_frames = request.max_frames
    if request.show_window and not show_window:
        LOGGER.warning("OpenCV sin soporte GUI; se ejecuta en modo headless (sin ventana).")
        if max_frames <= 0:
            max_frames = 300
            LOGGER.warning("Modo headless sin --frames: se limita a %d fotogramas.", max_frames)

    try:
        if not show_window and max_frames <= 0:
            msg = "Sin ventana no hay ESC: usa --frames > 0 junto con --no-window."
            raise RecognizerError(msg)
        with log_step(LOGGER, "Cargando configuracion"):
            config_path = prepare_workspace(request.config_path)
            app_config = load_config(config_path)
            camera_config = resolve_camera_config(
                app_config=app_config, device_override=request.device
            )
            ocr_config = app_config.ocr_reader

        roi = ROI(
            x_min=ocr_config.roi_x_min,
            y_min=ocr_config.roi_y_min,
            x_max=ocr_config.roi_x_max,
            y_max=ocr_config.roi_y_max,
        )
        engine = EasyOCREngine(
            languages=ocr_config.languages,
            min_confidence=ocr_config.min_confidence,
            max_results=ocr_config.max_results,
            max_width=ocr_config.max_width,
            canvas_size=ocr_config.canvas_size,
            mag_ratio=ocr_config.mag_ratio,
        )
        pipeline = PipelineBuilder().build()
        state = _OCRState(roi=roi)

        def _on_result(boxes: tuple[OCRBox, ...]) -> None:
            state.boxes = boxes
            state.texts = tuple(box.text for box in boxes)

        def _on_context(context: FrameContext) -> None:
            if worker.error is not None:
                raise worker.error
            draw_ocr_overlay(
                context.frame.data,
                boxes=state.boxes,
                roi=state.roi,
                texts=state.texts,
            )

        def _on_progress(count: int, fps: float) -> None:
            LOGGER.info(
                "Fotogramas: %d | FPS medio: %.1f | Textos: %d",
                count,
                fps,
                len(state.texts),
            )

        with ExitStack() as stack:
            camera = OpenCVCamera(camera_config)
            with log_step(LOGGER, f"Abriendo camara (device={camera_config.device_index})"):
                # LatestFrameSource abre la camara y arranca el hilo de captura;
                # no se entra la camara aparte (seria una doble apertura).
                source = stack.enter_context(LatestFrameSource(camera))
            with log_step(LOGGER, "Cargando motor EasyOCR"):
                engine.open()
                stack.callback(engine.close)
            worker = stack.enter_context(
                _OCRWorker(
                    source=source,
                    engine=engine,
                    roi=roi,
                    process_every_n_frames=ocr_config.process_every_n_frames,
                    on_result=_on_result,
                    logger=LOGGER,
                    max_inference_fps=ocr_config.max_inference_fps,
                    change_threshold=ocr_config.change_threshold,
                    max_frame_width=ocr_config.max_frame_width,
                )
            )
            LOGGER.info("Listo. Pulsa ESC o q para volver al menu.")
            frames, fps = run_camera_loop(
                source,
                pipeline=pipeline,
                window_name=WINDOW_NAME,
                show_window=show_window,
                max_frames=max_frames,
                callbacks=RuntimeCallbacks(
                    on_context=_on_context,
                    on_progress=_on_progress,
                ),
            )
    except RecognizerError as exc:
        LOGGER.error("La app fallo: %s", exc)
        return 1
    except Exception:
        LOGGER.exception("Error inesperado en la app de OCR")
        return 1
    finally:
        if show_window:
            with contextlib.suppress(cv2.error):
                cv2.destroyAllWindows()

    LOGGER.info(
        "App OK: %d fotogramas, %.1f FPS medio, textos detectados: %d.",
        frames,
        fps,
        len(state.texts),
    )
    return 0
