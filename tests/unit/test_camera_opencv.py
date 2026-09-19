"""Tests del adaptador de camara OpenCV con un doble de VideoCapture."""

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray

from recognizer.adapters.camera_opencv import OpenCVCamera
from recognizer.core.config import CameraConfig
from recognizer.core.constants import DEFAULT_CAPTURE_BUFFER_SIZE
from recognizer.core.errors import CameraError

FRAME_SHAPE = (4, 6, 3)
FRAME_WIDTH = 6
FRAME_HEIGHT = 4
EXPECTED_SET_CALLS = 4


class FakeCapture:
    """Doble de cv2.VideoCapture con fotogramas sinteticos."""

    def __init__(self, *, opened: bool = True, frames: int = 2) -> None:
        self._opened = opened
        self._frames = frames
        self.released = False
        self.set_calls: list[tuple[int, float]] = []
        self.read_calls = 0

    def isOpened(self) -> bool:
        return self._opened

    def read(self) -> tuple[bool, NDArray[np.uint8] | None]:
        self.read_calls += 1
        if self.read_calls > self._frames:
            return False, None
        return True, np.zeros(FRAME_SHAPE, dtype=np.uint8)

    def set(self, prop_id: int, value: float) -> bool:
        self.set_calls.append((prop_id, value))
        return True

    def release(self) -> None:
        self.released = True


def _camera(fake: FakeCapture) -> OpenCVCamera:
    return OpenCVCamera(CameraConfig(), capture_factory=lambda _index: fake)


def test_open_configures_capture_and_reads_frames() -> None:
    fake = FakeCapture(frames=2)
    with _camera(fake) as camera:
        first = camera.read()
        second = camera.read()
        third = camera.read()

    assert first is not None
    assert second is not None
    assert third is None
    assert (first.width, first.height) == (FRAME_WIDTH, FRAME_HEIGHT)
    assert fake.released
    assert len(fake.set_calls) == EXPECTED_SET_CALLS


def test_open_sets_minimal_capture_buffer_to_avoid_latency() -> None:
    fake = FakeCapture()
    camera = _camera(fake)
    camera.open()
    camera.release()

    assert (cv2.CAP_PROP_BUFFERSIZE, float(DEFAULT_CAPTURE_BUFFER_SIZE)) in fake.set_calls


def test_open_fails_when_device_is_not_available() -> None:
    fake = FakeCapture(opened=False)
    camera = _camera(fake)
    with pytest.raises(CameraError):
        camera.open()
    assert fake.released


def test_opening_twice_raises() -> None:
    camera = _camera(FakeCapture())
    camera.open()
    with pytest.raises(CameraError):
        camera.open()
    camera.release()


def test_read_without_open_raises() -> None:
    camera = _camera(FakeCapture())
    with pytest.raises(CameraError):
        camera.read()


def test_release_is_idempotent_and_updates_is_open() -> None:
    camera = _camera(FakeCapture())
    camera.open()
    assert camera.is_open
    camera.release()
    camera.release()
    assert not camera.is_open


def test_timestamps_are_monotonic() -> None:
    camera = _camera(FakeCapture(frames=2))
    camera.open()
    first = camera.read()
    second = camera.read()
    camera.release()
    assert first is not None
    assert second is not None
    assert second.timestamp >= first.timestamp
