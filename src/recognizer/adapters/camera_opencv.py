"""Adaptador de camara basado en OpenCV."""

from collections.abc import Callable
from time import perf_counter
from typing import Protocol, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.core.config import CameraConfig
from recognizer.core.domain.frame import Frame
from recognizer.core.errors import CameraError
from recognizer.core.ports.frame_source import FrameSource

CaptureReadResult = tuple[bool, NDArray[np.uint8] | None]


class CaptureDevice(Protocol):
    """Subconjunto de cv2.VideoCapture que usamos (permite fakes en tests)."""

    def isOpened(self) -> bool:  # noqa: N802 - nombre de la API de OpenCV
        """Indica si el dispositivo esta abierto."""
        ...

    def read(self) -> CaptureReadResult:
        """Lee un fotograma del dispositivo."""
        ...

    def set(self, prop_id: int, value: float) -> bool:
        """Ajusta una propiedad del dispositivo."""
        ...

    def release(self) -> None:
        """Libera el dispositivo."""
        ...


CaptureFactory = Callable[[int], CaptureDevice]


def _default_capture_factory(device_index: int) -> CaptureDevice:
    # cv2.VideoCapture cumple el protocolo y sus tipos no son invariantes,
    # por eso el cast explicito en la frontera con la libreria.
    return cast("CaptureDevice", cv2.VideoCapture(device_index))


class OpenCVCamera(FrameSource):
    """Fuente de fotogramas para una camara local via OpenCV."""

    def __init__(
        self,
        config: CameraConfig,
        capture_factory: CaptureFactory | None = None,
    ) -> None:
        self._config = config
        self._capture_factory = capture_factory or _default_capture_factory
        self._capture: CaptureDevice | None = None

    def open(self) -> None:
        """Abre el dispositivo y aplica resolucion y fps configurados.

        Raises:
            CameraError: si el dispositivo no puede abrirse o ya estaba abierto.
        """
        if self._capture is not None:
            msg = "La camara ya esta abierta."
            raise CameraError(msg)

        capture = self._capture_factory(self._config.device_index)
        if not capture.isOpened():
            capture.release()
            msg = (
                f"No se pudo abrir la camara (device_index={self._config.device_index}). "
                "Revisa que no este en uso por otra aplicacion y los permisos de camara."
            )
            raise CameraError(msg)

        capture.set(cv2.CAP_PROP_FRAME_WIDTH, float(self._config.width))
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self._config.height))
        capture.set(cv2.CAP_PROP_FPS, float(self._config.target_fps))
        self._capture = capture

    def read(self) -> Frame | None:
        """Lee un fotograma; None si la camara fallo en este intento.

        Raises:
            CameraError: si se intenta leer sin haber abierto la camara.
        """
        if self._capture is None:
            msg = "La camara no esta abierta: llama a open() antes de read()."
            raise CameraError(msg)

        ok, data = self._capture.read()
        if not ok or data is None:
            return None
        return Frame(data=data, timestamp=perf_counter())

    def release(self) -> None:
        """Libera el dispositivo si esta abierto."""
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    @property
    def is_open(self) -> bool:
        """Indica si el dispositivo esta abierto."""
        return self._capture is not None and self._capture.isOpened()

    def __enter__(self) -> "OpenCVCamera":
        self.open()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()
