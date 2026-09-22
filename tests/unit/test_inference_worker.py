"""Tests del worker generico de inferencia (sin hardware)."""

from __future__ import annotations

import logging
import time
from collections import deque

import numpy as np

from recognizer.adapters.latest_frame_source import LatestFrameSource
from recognizer.cli.inference_worker import LatestInferenceWorker
from recognizer.core.domain.frame import Frame
from recognizer.core.errors import RecognizerError

FRAME_SHAPE = (2, 3, 3)
TIMEOUT = 2.0
TEST_LOGGER = logging.getLogger("test.inference.worker")


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
    processed: list[int] = []
    with source:
        worker = LatestInferenceWorker(
            source=source,
            infer=lambda frame: int(frame.data[0, 0, 0]),
            on_result=processed.append,
            logger=TEST_LOGGER,
        )
        with worker:
            fake.push(7)
            assert _wait_until(lambda: bool(processed))
        assert worker.error is None

    assert processed[0] == 7


def test_worker_throttles_inference_rate() -> None:
    fake = FakeSource()
    source = LatestFrameSource(fake, read_timeout=0.5, join_timeout=1.0, failure_sleep=0.001)
    processed: list[int] = []
    with source:
        worker = LatestInferenceWorker(
            source=source,
            infer=lambda frame: int(frame.data[0, 0, 0]),
            on_result=processed.append,
            logger=TEST_LOGGER,
            max_inference_fps=1.0,
        )
        with worker:
            fake.push(1)
            assert _wait_until(lambda: bool(processed))
            for value in range(2, 8):
                fake.push(value)
            time.sleep(0.15)
        assert worker.error is None

    assert len(processed) == 1


def test_worker_captures_inference_error() -> None:
    fake = FakeSource()
    source = LatestFrameSource(fake, read_timeout=0.5, join_timeout=1.0, failure_sleep=0.001)

    def _boom(_frame: Frame) -> int:
        msg = "fallo simulado"
        raise RuntimeError(msg)

    with source:
        worker = LatestInferenceWorker(
            source=source,
            infer=_boom,
            on_result=lambda _value: None,
            logger=TEST_LOGGER,
        )
        with worker:
            fake.push(1)
            assert _wait_until(lambda: worker.error is not None)

    assert isinstance(worker.error, RecognizerError)
