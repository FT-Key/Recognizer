"""Puerto de motor OCR."""

from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from recognizer.core.domain.ocr import ROI, OCRBox


class OCRConfig(Protocol):
    """Parametros minimos que necesita el motor OCR."""

    min_confidence: float
    max_results: int


class OCREngine(Protocol):
    """Motor OCR que extrae texto de un recorte de imagen."""

    def open(self) -> None:
        """Prepara el motor y carga los modelos."""
        ...

    def read(
        self,
        image_rgb: NDArray[np.uint8],
        roi: ROI,
        *,
        frame_width: int,
        frame_height: int,
    ) -> tuple[OCRBox, ...]:
        """Lee texto en la ROI del fotograma (formato RGB)."""
        ...

    def close(self) -> None:
        """Libera los recursos del motor."""
        ...
