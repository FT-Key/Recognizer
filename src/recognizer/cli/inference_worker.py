"""Worker generico de inferencia asincrona sobre el ultimo fotograma.

Envuelve un ``LatestFrameSource`` y corre una inferencia en un hilo aparte,
entregando el resultado al llamador. El bucle principal **solo dibuja**, asi que
la vista va a ritmo de camara aunque la inferencia tarde (mismo patron que la
app facial y el OCR; ver la seccion de latencia en ``docs/ARCHITECTURE.md``).
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from recognizer.adapters.latest_frame_source import LatestFrameSource
from recognizer.core.constants import (
    INFERENCE_WORKER_JOIN_TIMEOUT_SECONDS,
    INFERENCE_WORKER_WAIT_TIMEOUT_SECONDS,
)
from recognizer.core.domain.frame import Frame
from recognizer.core.errors import RecognizerError


class LatestInferenceWorker[T]:
    """Corre ``infer`` sobre el fotograma mas reciente y entrega el resultado.

    Toma fotogramas de ``LatestFrameSource`` sin consumirlos (version propia),
    asi que una inferencia lenta no frena la lectura de la camara: cuando el
    worker termina, retoma el fotograma mas nuevo y salta los intermedios.
    """

    def __init__(
        self,
        *,
        source: LatestFrameSource,
        infer: Callable[[Frame], T],
        on_result: Callable[[T], None],
        logger: logging.Logger,
        name: str = "recognizer-infer",
        process_every_n_frames: int = 1,
        max_inference_fps: float = 0.0,
    ) -> None:
        self._source = source
        self._infer = infer
        self._on_result = on_result
        self._logger = logger
        self._name = name
        self._every = max(1, process_every_n_frames)
        self._min_interval = 1.0 / max_inference_fps if max_inference_fps > 0 else 0.0
        self._last_inference = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._error: RecognizerError | None = None

    def start(self) -> None:
        """Arranca el hilo de inferencia."""
        self._thread = threading.Thread(target=self._run, name=self._name, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        version = 0
        seen = 0
        while not self._stop.is_set():
            got = self._source.wait_for_new(version, timeout=INFERENCE_WORKER_WAIT_TIMEOUT_SECONDS)
            if got is None:
                continue
            frame, version = got
            seen += 1
            if seen % self._every != 0:
                continue
            now = time.monotonic()
            if self._min_interval > 0 and now - self._last_inference < self._min_interval:
                continue
            self._last_inference = now
            try:
                result = self._infer(frame)
            except Exception as exc:  # el hilo no debe morir en silencio
                error = (
                    exc
                    if isinstance(exc, RecognizerError)
                    else RecognizerError(f"Fallo la inferencia: {exc}")
                )
                self._error = error
                self._logger.error("Fallo la inferencia: %s", exc)
                self._stop.set()
                return
            if self._stop.is_set():
                return
            self._on_result(result)

    def stop(self) -> None:
        """Detiene el hilo y espera a que termine."""
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=INFERENCE_WORKER_JOIN_TIMEOUT_SECONDS)
            if thread.is_alive():
                self._logger.warning(
                    "El worker de inferencia no termino en %.1fs; se continua el cierre.",
                    INFERENCE_WORKER_JOIN_TIMEOUT_SECONDS,
                )
            self._thread = None

    @property
    def error(self) -> RecognizerError | None:
        """Error de inferencia capturado en el worker, si lo hubo."""
        return self._error

    def __enter__(self) -> LatestInferenceWorker[T]:
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stop()
