"""Enumerador de camaras locales basado en OpenCV (imperative shell).

Prueba indices ``0..max_index`` con ``cv2.VideoCapture(i)`` + ``read()`` y
devuelve las que abren y entregan un fotograma. ``cv2`` se importa dentro del
metodo para que el menu no cargue vision hasta pulsar "Detectar".
"""

import logging

from recognizer.core.constants import DEFAULT_CAMERA_ENUMERATOR_MAX_INDEX
from recognizer.core.domain.camera import CameraInfo
from recognizer.core.ports.camera_discovery import CameraEnumerator

LOGGER = logging.getLogger("recognizer.camera_discovery")

CAMERA_LABEL_TEMPLATE = "Cámara {index}"


class OpenCVCameraEnumerator(CameraEnumerator):
    """Detecta camaras probando indices de OpenCV de forma secuencial."""

    def __init__(self, max_index: int = DEFAULT_CAMERA_ENUMERATOR_MAX_INDEX) -> None:
        if max_index < 0:
            msg = f"La enumeracion requiere max_index >= 0 (llego {max_index})."
            raise ValueError(msg)
        self._max_index = max_index

    def list_cameras(self) -> tuple[CameraInfo, ...]:
        """Prueba cada indice y devuelve las camaras que entregan fotograma."""
        import cv2

        found: list[CameraInfo] = []
        for index in range(self._max_index + 1):
            capture = cv2.VideoCapture(index)
            try:
                if not capture.isOpened():
                    continue
                ok, frame = capture.read()
                if not ok or frame is None:
                    continue
                found.append(
                    CameraInfo(index=index, label=CAMERA_LABEL_TEMPLATE.format(index=index))
                )
            finally:
                capture.release()
        LOGGER.info("Camaras detectadas: %d.", len(found))
        return tuple(found)
