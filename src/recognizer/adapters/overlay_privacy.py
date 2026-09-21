"""Overlay de privacidad: difumina los rostros y dibuja su marco y el HUD.

El difuminado es el efecto de la app (anonimiza caras en vivo); el marco y el
HUD solo comunican que la privacidad esta activa. La matematica de regiones y
kernels vive en `core/domain/privacy.py`; aqui solo se aplica con OpenCV.
"""

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.core.constants import DEFAULT_PRIVACY_FACE_MARGIN
from recognizer.core.domain.face import FaceBox
from recognizer.core.domain.privacy import (
    PixelRect,
    effective_blur_kernel,
    face_blur_regions,
)

BOX_COLOR_BGR = (0, 200, 120)
BOX_THICKNESS = 2
LABEL_TEMPLATE = "privacidad"
LABEL_FONT = cv2.FONT_HERSHEY_SIMPLEX
LABEL_SCALE = 0.5
LABEL_THICKNESS = 1
LABEL_MARGIN_PX = 6
HUD_FONT = cv2.FONT_HERSHEY_SIMPLEX
HUD_SCALE = 0.9
HUD_THICKNESS = 2
HUD_COLOR_BGR = (0, 200, 120)
HUD_POSITION = (10, 30)
HUD_TEMPLATE = "Rostros difuminados: {count}"
GAUSSIAN_SIGMA = 0.0


def blur_faces(
    image: NDArray[np.uint8],
    *,
    boxes: tuple[FaceBox, ...],
    blur_strength: int,
    margin_ratio: float = DEFAULT_PRIVACY_FACE_MARGIN,
) -> tuple[PixelRect, ...]:
    """Difumina cada caja facial sobre el fotograma (in place).

    Devuelve los rectangulos efectivamente difuminados; las cajas demasiado
    pequenas para un kernel valido se omiten.
    """
    height, width = image.shape[:2]
    regions = face_blur_regions(
        boxes,
        width=width,
        height=height,
        margin_ratio=margin_ratio,
    )
    blurred: list[PixelRect] = []
    for rect in regions:
        kernel = effective_blur_kernel(strength=blur_strength, rect=rect)
        if kernel == 0:
            continue
        roi = image[rect.y_min : rect.y_max, rect.x_min : rect.x_max]
        image[rect.y_min : rect.y_max, rect.x_min : rect.x_max] = cv2.GaussianBlur(
            roi,
            (kernel, kernel),
            GAUSSIAN_SIGMA,
        )
        blurred.append(rect)
    return tuple(blurred)


def draw_privacy_overlay(
    image: NDArray[np.uint8],
    *,
    regions: tuple[PixelRect, ...],
    blurred: int,
) -> None:
    """Dibuja el marco de cada region difuminada y el HUD con el total."""
    for rect in regions:
        cv2.rectangle(
            image,
            (rect.x_min, rect.y_min),
            (rect.x_max, rect.y_max),
            BOX_COLOR_BGR,
            BOX_THICKNESS,
        )
        cv2.putText(
            image,
            LABEL_TEMPLATE,
            (rect.x_min, max(rect.y_min - LABEL_MARGIN_PX, 0)),
            LABEL_FONT,
            LABEL_SCALE,
            BOX_COLOR_BGR,
            LABEL_THICKNESS,
        )
    cv2.putText(
        image,
        HUD_TEMPLATE.format(count=blurred),
        HUD_POSITION,
        HUD_FONT,
        HUD_SCALE,
        HUD_COLOR_BGR,
        HUD_THICKNESS,
    )
