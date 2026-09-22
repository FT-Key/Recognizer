"""OCR en vivo (dominio puro).

Un ``OCRReader`` recorta una region de interes (ROI) del fotograma y devuelve
los textos detectados con sus cajas y confianza. El motor de OCR es inyectado
via el puerto ``OCREngine``; la app usa EasyOCR pero otro motor cualquiera
serviria.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OCRBox:
    """Caja delimitadora de un texto detectado, en coordenadas absolutas (px)."""

    x_min: int
    y_min: int
    x_max: int
    y_max: int
    text: str
    confidence: float


@dataclass(frozen=True, slots=True)
class ROI:
    """Region de interes normalizada 0..1 sobre el fotograma."""

    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def pixel_rect(self, frame_width: int, frame_height: int) -> tuple[int, int, int, int]:
        """Convierte la ROI a coordenadas absolutas (x1, y1, x2, y2)."""
        return (
            int(self.x_min * frame_width),
            int(self.y_min * frame_height),
            int(self.x_max * frame_width),
            int(self.y_max * frame_height),
        )


@dataclass(frozen=True, slots=True)
class OCRSnapshot:
    """Resultado del OCR en un fotograma."""

    boxes: tuple[OCRBox, ...]
    texts: tuple[str, ...]
    roi: ROI
    processed: bool = True
