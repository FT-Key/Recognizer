"""Tests de la fuente de fotogramas asincrona (sin hardware).

Se usa una fuente falsa que entrega los fotogramas que el test empuja, de modo
que se verifica la semantica de "ultimo fotograma" sin abrir ninguna camara.
"""

from __future__ import annotations

import threading
import time
from collections import deque

import numpy as np

from recognizer.adapters.latest_frame_source import LatestFrameSource
from recognizer.core.domain.frame import Frame

FRAME_SHAPE = (2, 3, 3)
READ_TIMEOUT = 0.5
SHORT_TIMEOUT = 0.05


class FakeSource:
    """Fuente falsa que entrega los fotogramas empujados por el test."""

    def __init__(self) -> None:
        self.frames: deque[Frame] = deque()
        self.opened = False
        self.released = False

    def push(self, value: int) -> Frame:
        frame = Frame(
            data=np.full(FRAME_SHAPE, value, dtype=np.uint8),
            timestamp=float(value),
        )
        self.frames.append(frame)
        return frame

    def open(self) -> None:
        self.opened = True

    def read(self) -> Frame | None:
        return self.frames.popleft() if self.frames else None

    def release(self) -> None:
        self.released = True


def _source(fake: FakeSource, *, read_timeout: float = READ_TIMEOUT) -> LatestFrameSource:
    return LatestFrameSource(fake, read_timeout=read_timeout, join_timeout=1.0, failure_sleep=0.001)


def _wait_for_frame(source: LatestFrameSource, *, timeout: float = 1.0) -> Frame | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        frame = source.read()
        if frame is not None:
            return frame
    return None


def test_read_returns_a_copy_of_the_latest_frame() -> None:
    fake = FakeSource()
    source = _source(fake)
    with source:
        pushed = fake.push(7)
        received = _wait_for_frame(source)

    assert received is not None
    assert received.data is not pushed.data
    assert (received.data == 7).all()
    assert received.timestamp == pushed.timestamp


def test_read_does_not_repeat_the_same_frame() -> None:
    fake = FakeSource()
    source = _source(fake, read_timeout=SHORT_TIMEOUT)
    with source:
        fake.push(1)
        first = _wait_for_frame(source)
        second = source.read()
        fake.push(2)
        third = _wait_for_frame(source)

    assert first is not None
    assert (first.data == 1).all()
    assert second is None
    assert third is not None
    assert (third.data == 2).all()


def test_wait_for_new_returns_frame_and_advances_version() -> None:
    fake = FakeSource()
    source = _source(fake)
    with source:
        fake.push(3)
        got = source.wait_for_new(0, timeout=READ_TIMEOUT)
        assert got is not None
        frame, version = got
        assert (frame.data == 3).all()
        assert version >= 1
        assert source.wait_for_new(version, timeout=SHORT_TIMEOUT) is None


def test_read_returns_none_when_no_frame_arrives() -> None:
    fake = FakeSource()
    source = _source(fake, read_timeout=SHORT_TIMEOUT)
    with source:
        assert source.read() is None


def test_release_stops_thread_and_releases_source() -> None:
    fake = FakeSource()
    source = _source(fake)
    source.open()
    assert fake.opened
    source.release()
    assert fake.released
    threads = [thread.name for thread in threading.enumerate()]
    assert "recognizer-camera-drain" not in threads
