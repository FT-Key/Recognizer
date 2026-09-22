"""Adaptador EasyOCR: implementa OCREngine con EasyOCR."""

from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.core.domain.ocr import ROI, OCRBox

LOGGER = logging.getLogger("recognizer.easyocr")


class EasyOCREngine:
    """Motor OCR basado en EasyOCR.

    ``languages`` es una tupla de codigos de idioma (``"en"``, ``"es"``, etc.).
    El lector se crea en ``open()`` para cargar los modelos una sola vez.

    En CPU EasyOCR es lento y escala con los pixeles, asi que el recorte de la
    ROI se reduce a ``max_width`` antes de inferir y se limita el lienzo de CRAFT
    (``canvas_size``) sin reescalar (``mag_ratio``). ``max_width=0`` desactiva el
    reescalado.
    """

    def __init__(
        self,
        *,
        languages: tuple[str, ...] = ("en", "es"),
        min_confidence: float = 0.3,
        max_results: int = 20,
        max_width: int = 640,
        canvas_size: int = 1280,
        mag_ratio: float = 1.0,
    ) -> None:
        self._languages = languages
        self._min_confidence = min_confidence
        self._max_results = max_results
        self._max_width = max_width
        self._canvas_size = canvas_size
        self._mag_ratio = mag_ratio
        self._reader: Any | None = None

    def open(self) -> None:
        import easyocr

        LOGGER.info("Cargando modelos EasyOCR (idiomas: %s)...", self._languages)
        self._reader = easyocr.Reader(
            list(self._languages),
            gpu=False,
            verbose=False,
        )
        LOGGER.info("EasyOCR listo.")

    def read(
        self,
        image_rgb: NDArray[np.uint8],
        roi: ROI,
        *,
        frame_width: int,
        frame_height: int,
    ) -> tuple[OCRBox, ...]:
        if self._reader is None:
            return ()

        x1, y1, x2, y2 = roi.pixel_rect(frame_width, frame_height)
        crop = image_rgb[y1:y2, x1:x2]
        if crop.size == 0:
            return ()

        scale = 1.0
        if self._max_width > 0 and crop.shape[1] > self._max_width:
            scale = self._max_width / crop.shape[1]
            new_height = max(1, round(crop.shape[0] * scale))
            crop = cv2.resize(  # type: ignore[assignment]
                crop, (self._max_width, new_height), interpolation=cv2.INTER_AREA
            )

        results: list[Any] = self._reader.readtext(
            crop,
            paragraph=False,
            batch_size=1,
            mag_ratio=self._mag_ratio,
            canvas_size=self._canvas_size,
        )

        boxes: list[OCRBox] = []
        for item in results[: self._max_results]:
            if not isinstance(item, (list, tuple)) or len(item) < 3:
                continue
            raw_bbox = item[0]
            text = str(item[1])
            try:
                confidence = float(str(item[2]))
            except (TypeError, ValueError):
                continue
            if confidence < self._min_confidence:
                continue
            if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) < 4:
                continue
            pts = raw_bbox
            xs = [round(float(pt[0]) / scale) + x1 for pt in pts]
            ys = [round(float(pt[1]) / scale) + y1 for pt in pts]
            boxes.append(
                OCRBox(
                    x_min=min(xs),
                    y_min=min(ys),
                    x_max=max(xs),
                    y_max=max(ys),
                    text=text,
                    confidence=confidence,
                )
            )
        return tuple(boxes)

    def close(self) -> None:
        self._reader = None
