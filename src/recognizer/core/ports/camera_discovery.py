"""Puerto de descubrimiento de camaras locales.

El menu enumera las camaras sin abrir la seleccionada: el adaptador actual
prueba indices con OpenCV y el dominio solo ve ``CameraInfo``.
"""

from typing import Protocol

from recognizer.core.domain.camera import CameraInfo


class CameraEnumerator(Protocol):
    """Enumera las camaras locales que entregan fotogramas."""

    def list_cameras(self) -> tuple[CameraInfo, ...]:
        """Devuelve las camaras disponibles (vacio si no hay ninguna)."""
        ...
