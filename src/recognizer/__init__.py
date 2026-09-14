"""Recognizer: reconocimiento de rostro y gestos de manos por camara."""

import os

# Windows: OpenCV abre la camara con el backend MSMF, que con las "hardware
# transforms" activadas puede tardar 20-30 s. El backend lee esta variable al
# importar cv2, por eso debe fijarse ANTES de cualquier `import cv2`; como
# `recognizer` es el paquete raiz, se importa siempre primero. `setdefault`
# respeta un valor ya definido por el usuario.
os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

__version__ = "0.1.0"
