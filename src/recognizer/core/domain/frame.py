"""Fotograma capturado por una fuente de video."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class Frame:
    """Fotograma en formato BGR uint8 con su marca de tiempo."""

    data: NDArray[np.uint8]
    timestamp: float

    @property
    def width(self) -> int:
        """Ancho del fotograma en pixeles."""
        return int(self.data.shape[1])

    @property
    def height(self) -> int:
        """Alto del fotograma en pixeles."""
        return int(self.data.shape[0])
