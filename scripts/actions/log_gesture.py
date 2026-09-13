"""Registra cada gesto confirmado en scripts/actions/gesture_log.txt.

Script de ejemplo sin dependencias externas, pensado para usarse desde
config.yaml con contexto:

    actions:
      mappings:
        ILoveYou:
          type: script
          path: scripts/actions/log_gesture.py
          pass_context: true
"""

import os
from datetime import datetime
from pathlib import Path

ENV_GESTURE = "RECOGNIZER_GESTURE"
ENV_HANDEDNESS = "RECOGNIZER_HANDEDNESS"
ENV_CONFIDENCE = "RECOGNIZER_CONFIDENCE"
ENV_TIMESTAMP = "RECOGNIZER_TIMESTAMP"

LOG_FILE_NAME = "gesture_log.txt"
NO_CONTEXT = "sin contexto"
UNKNOWN = "?"

LOG_PATH = Path(__file__).resolve().parent / LOG_FILE_NAME


def _context() -> str:
    gesture = os.environ.get(ENV_GESTURE)
    if gesture is None:
        return NO_CONTEXT
    handedness = os.environ.get(ENV_HANDEDNESS, UNKNOWN)
    confidence = os.environ.get(ENV_CONFIDENCE, UNKNOWN)
    timestamp = os.environ.get(ENV_TIMESTAMP, UNKNOWN)
    return (
        f"gesture={gesture} handedness={handedness} confidence={confidence} timestamp={timestamp}"
    )


def main() -> None:
    """Anade una linea con el contexto del gesto y el instante local."""
    now = datetime.now().isoformat(timespec="seconds")
    with LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(f"{now} | {_context()}\n")


if __name__ == "__main__":
    main()
