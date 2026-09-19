"""Camaras disponibles del equipo (dominio puro).

Vocabulario minimo para el selector de camara del menu: cada camara se
identifica por su indice de dispositivo y una etiqueta legible.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CameraInfo:
    """Camara detectada: indice de dispositivo y etiqueta para el menu."""

    index: int
    label: str
