"""Overlay de edad y genero: dibuja la caja, la etiqueta y el HUD de cada rostro.

La estimacion y el suavizado viven en `core/domain/face_attributes.py`; aqui
solo se dibuja con OpenCV sobre el fotograma.
"""

import cv2
import numpy as np
from numpy.typing import NDArray

from recognizer.core.domain.face_attributes import FaceAttributes

BOX_COLOR_BGR = (0, 200, 120)
BOX_THICKNESS = 2
LABEL_FONT = cv2.FONT_HERSHEY_SIMPLEX
LABEL_SCALE = 0.6
LABEL_THICKNESS = 1
LABEL_MARGIN_PX = 6
LABEL_TEMPLATE = "{gender} ~{age}"
HUD_FONT = cv2.FONT_HERSHEY_SIMPLEX
HUD_SCALE = 0.9
HUD_THICKNESS = 2
HUD_COLOR_BGR = (0, 200, 120)
HUD_POSITION = (10, 30)
HUD_TEMPLATE = "Rostros: {count}"


def draw_gender_age_overlay(
    image: NDArray[np.uint8],
    *,
    faces: tuple[FaceAttributes, ...],
) -> None:
    """Dibuja la caja y la etiqueta de cada rostro, y el HUD con el total."""
    height, width = image.shape[:2]
    for face in faces:
        x_min = int(face.box.x_min * width)
        y_min = int(face.box.y_min * height)
        x_max = int(face.box.x_max * width)
        y_max = int(face.box.y_max * height)
        cv2.rectangle(
            image,
            (x_min, y_min),
            (x_max, y_max),
            BOX_COLOR_BGR,
            BOX_THICKNESS,
        )
        cv2.putText(
            image,
            LABEL_TEMPLATE.format(gender=face.gender.value, age=face.age),
            (x_min, max(y_min - LABEL_MARGIN_PX, 0)),
            LABEL_FONT,
            LABEL_SCALE,
            BOX_COLOR_BGR,
            LABEL_THICKNESS,
        )
    cv2.putText(
        image,
        HUD_TEMPLATE.format(count=len(faces)),
        HUD_POSITION,
        HUD_FONT,
        HUD_SCALE,
        HUD_COLOR_BGR,
        HUD_THICKNESS,
    )
