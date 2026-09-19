"""Codificacion de imagenes BGR a PNG en memoria (OpenCV).

Aisla `cv2` para que los runners y la GUI obtengan bytes PNG sin conocer la
libreria. Los adaptadores de persistencia reciben esos bytes ya codificados.
"""

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.core.errors import ImageEncodingError

PNG_EXTENSION = ".png"


def encode_png(image: NDArray[np.uint8]) -> bytes:
    """Codifica una imagen BGR uint8 como PNG en memoria.

    Raises:
        ImageEncodingError: si OpenCV no puede codificar la imagen.
    """
    try:
        ok, buffer = cv2.imencode(PNG_EXTENSION, image)
    except cv2.error as exc:
        msg = "No se pudo codificar la imagen como PNG."
        raise ImageEncodingError(msg) from exc
    if not ok:
        msg = "No se pudo codificar la imagen como PNG."
        raise ImageEncodingError(msg)
    return bytes(buffer.tobytes())
