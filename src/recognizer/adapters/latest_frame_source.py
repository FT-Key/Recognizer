"""Fuente de fotogramas con hilo de captura y ultimo fotograma disponible.

Envuelve cualquier ``FrameSource`` y lanza un hilo daemon que la drena sin
parar, guardando solo el fotograma mas reciente. El bucle de dibujo usa
``read`` (bloquea hasta el siguiente fotograma nuevo y devuelve una copia) y el
worker de inferencia usa ``wait_for_new`` (no consume). Asi una inferencia lenta
no frena la lectura de la camara y el stream de red (p. ej. camara del telefono)
se mantiene drenado, sin retraso creciente ni avisos de "calidad de red".
"""

from __future__ import annotations

import logging
import threading
import time

from recognizer.core.constants import (
    LATEST_FRAME_FAILURE_SLEEP_SECONDS,
    LATEST_FRAME_JOIN_TIMEOUT_SECONDS,
    LATEST_FRAME_READ_TIMEOUT_SECONDS,
)
from recognizer.core.domain.frame import Frame
from recognizer.core.ports.frame_source import FrameSource

LOGGER = logging.getLogger("recognizer.camera.latest")


class LatestFrameSource(FrameSource):
    """Fuente con hilo de captura que expone siempre el fotograma mas reciente."""

    def __init__(
        self,
        source: FrameSource,
        *,
        read_timeout: float = LATEST_FRAME_READ_TIMEOUT_SECONDS,
        join_timeout: float = LATEST_FRAME_JOIN_TIMEOUT_SECONDS,
        failure_sleep: float = LATEST_FRAME_FAILURE_SLEEP_SECONDS,
    ) -> None:
        self._source = source
        self._condition = threading.Condition()
        self._latest: Frame | None = None
        self._version = 0
        self._consumed = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._read_timeout = read_timeout
        self._join_timeout = join_timeout
        self._failure_sleep = failure_sleep

    def open(self) -> None:
        """Abre la fuente envuelta y arranca el hilo de captura."""
        self._source.open()
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._drain, name="recognizer-camera-drain", daemon=True
        )
        self._thread.start()

    def _drain(self) -> None:
        """Lee la fuente sin parar y publica el ultimo fotograma disponible.

        Si la fuente falla (p. ej. se libera mientras el hilo lee), el hilo
        termina en silencio; el bucle de dibujo recibira ``None`` y decidira.
        """
        try:
            while not self._stop.is_set():
                frame = self._source.read()
                if frame is None:
                    time.sleep(self._failure_sleep)
                    continue
                with self._condition:
                    self._latest = frame
                    self._version += 1
                    self._condition.notify_all()
        except Exception as exc:  # el hilo jamas debe propagar al proceso
            LOGGER.debug("Hilo de captura detenido (%s).", exc)

    def read(self) -> Frame | None:
        """Espera al siguiente fotograma nuevo y devuelve una copia para dibujar.

        Devuelve ``None`` si se agota el tiempo de espera (la camara no entrega
        fotogramas). La copia evita que el dibujo del overlay compita con la
        lectura de la misma imagen por parte del worker de inferencia.
        """
        with self._condition:
            available = self._condition.wait_for(
                lambda: self._version != self._consumed,
                timeout=self._read_timeout,
            )
            if not available or self._latest is None:
                return None
            self._consumed = self._version
            latest = self._latest
        return Frame(data=latest.data.copy(), timestamp=latest.timestamp)

    def wait_for_new(
        self, after_version: int, *, timeout: float | None = None
    ) -> tuple[Frame, int] | None:
        """Espera a un fotograma mas nuevo que ``after_version`` (no consume).

        Pensado para el worker de inferencia: devuelve el fotograma mas reciente
        junto a su version para que el worker no reprocese el mismo fotograma.
        Devuelve el fotograma sin copiar: el consumidor debe tratarlo como solo
        lectura (OpenCVCamera entrega un array nuevo en cada ``read``).
        """
        with self._condition:
            available = self._condition.wait_for(
                lambda: self._version > after_version and self._latest is not None,
                timeout=self._read_timeout if timeout is None else timeout,
            )
            if not available or self._latest is None:
                return None
            return self._latest, self._version

    def release(self) -> None:
        """Detiene el hilo de captura y libera la fuente envuelta."""
        self._stop.set()
        with self._condition:
            self._condition.notify_all()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=self._join_timeout)
            self._thread = None
        self._source.release()

    @property
    def latest_version(self) -> int:
        """Version del ultimo fotograma publicado (0 si aun no hay)."""
        with self._condition:
            return self._version

    def __enter__(self) -> LatestFrameSource:
        self.open()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()
