"""Descarga los modelos .task de MediaPipe usados por el proyecto.

Uso: uv run python scripts/download_models.py
"""

import sys
import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

MODELS: dict[str, str] = {
    "hand_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
        "hand_landmarker/float16/latest/hand_landmarker.task"
    ),
    "gesture_recognizer.task": (
        "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/"
        "gesture_recognizer/float16/latest/gesture_recognizer.task"
    ),
    "blaze_face_short_range.tflite": (
        "https://storage.googleapis.com/mediapipe-models/face_detector/"
        "blaze_face_short_range/float16/latest/blaze_face_short_range.tflite"
    ),
}

MEGABYTE = 1_048_576


def download(name: str, url: str) -> None:
    """Descarga un modelo si no existe todavia."""
    destination = MODELS_DIR / name
    if destination.is_file() and destination.stat().st_size > 0:
        print(f"OK (ya existe): {name}")
        return

    print(f"Descargando {name} ...")
    urllib.request.urlretrieve(url, destination)  # noqa: S310 - URLs https fijas
    size_mb = destination.stat().st_size / MEGABYTE
    print(f"OK: {name} ({size_mb:.1f} MB)")


def main() -> int:
    """Descarga todos los modelos del catalogo."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in MODELS.items():
        download(name, url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
