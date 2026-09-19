"""Tests del worker de inferencia facial (sin hardware ni InsightFace)."""

from __future__ import annotations

import logging
import time
from collections import deque

import numpy as np

from recognizer.adapters.latest_frame_source import LatestFrameSource
from recognizer.cli.apps.face_auth import _RecognitionWorker
from recognizer.core.domain.face import FaceBox, FaceObservation
from recognizer.core.domain.frame import Frame
from recognizer.core.errors import FaceRecognizerError

FRAME_SHAPE = (2, 3, 3)
TIMEOUT = 2.0
TEST_LOGGER = logging.getLogger("test.face.worker")


class FakeSource:
    """Fuente falsa que entrega los fotogramas empujados por el test."""

    def __init__(self) -> None:
        self.frames: deque[Frame] = deque()

    def push(self, value: int) -> None:
        self.frames.append(
            Frame(data=np.full(FRAME_SHAPE, value, dtype=np.uint8), timestamp=float(value))
        )

    def open(self) -> None:
        pass

    def read(self) -> Frame | None:
        return self.frames.popleft() if self.frames else None

    def release(self) -> None:
        pass


def _observation() -> FaceObservation:
    return FaceObservation(
        embedding=(1.0, 0.0),
        box=FaceBox(x_min=0.25, y_min=0.25, x_max=0.5, y_max=0.5, confidence=0.9),
        sharpness=120.0,
    )


class FakeRecognizer:
    """Reconocedor falso: cuenta llamadas y devuelve una observacion."""

    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self._fail = fail

    def recognize(self, _frame: Frame) -> tuple[FaceObservation, ...]:
        self.calls += 1
        if self._fail:
            msg = "fallo simulado"
            raise FaceRecognizerError(msg)
        return (_observation(),)


def _wait_until(predicate: object, *, timeout: float = TIMEOUT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if callable(predicate) and predicate():
            return True
        time.sleep(0.01)
    return False


def test_worker_processes_latest_frame_and_stops() -> None:
    fake = FakeSource()
    source = LatestFrameSource(fake, read_timeout=0.5, join_timeout=1.0, failure_sleep=0.001)
    recognizer = FakeRecognizer()
    processed: list[int] = []
    with source:
        worker = _RecognitionWorker(
            source=source,
            recognizer=recognizer,  # type: ignore[arg-type]
            process=lambda observations: processed.append(len(observations)),
            process_every_n_frames=1,
            logger=TEST_LOGGER,
        )
        with worker:
            fake.push(1)
            assert _wait_until(lambda: bool(processed))
        assert worker.error is None

    assert processed[0] == 1
    assert recognizer.calls >= 1


def test_worker_captures_inference_error() -> None:
    fake = FakeSource()
    source = LatestFrameSource(fake, read_timeout=0.5, join_timeout=1.0, failure_sleep=0.001)
    recognizer = FakeRecognizer(fail=True)
    with source:
        worker = _RecognitionWorker(
            source=source,
            recognizer=recognizer,  # type: ignore[arg-type]
            process=lambda _observations: None,
            process_every_n_frames=1,
            logger=TEST_LOGGER,
        )
        with worker:
            fake.push(1)
            assert _wait_until(lambda: worker.error is not None)

    assert isinstance(worker.error, FaceRecognizerError)
