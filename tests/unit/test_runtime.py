"""Tests del bucle de camara compartido, sin ventana ni hardware real."""

from collections.abc import Sequence

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray

from recognizer.cli.runtime import RuntimeCallbacks, run_camera_loop
from recognizer.core.constants import (
    ESC_KEY,
    FPS_LOG_INTERVAL,
    MAX_CONSECUTIVE_READ_FAILURES,
)
from recognizer.core.domain.frame import Frame
from recognizer.core.errors import CameraError
from recognizer.core.pipeline.builder import Pipeline
from recognizer.core.pipeline.context import FrameContext

FRAME_TIMESTAMP = 1.0
FRAME_SHAPE = (4, 6, 3)
QUIT_KEY = ord("q")
TOGGLE_KEY = ord("a")


class FakeCamera:
    """Fuente de fotogramas que sigue un guion de lecturas."""

    def __init__(self, reads: Sequence[Frame | None]) -> None:
        self._reads = list(reads)
        self.read_calls = 0

    def open(self) -> None:
        pass

    def read(self) -> Frame | None:
        self.read_calls += 1
        if self._reads:
            return self._reads.pop(0)
        return None

    def release(self) -> None:
        pass


def _frame(timestamp: float = FRAME_TIMESTAMP) -> Frame:
    data: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    return Frame(data=data, timestamp=timestamp)


def _pipeline() -> Pipeline:
    return Pipeline(processors=())


def test_loop_processes_max_frames_and_returns_positive_fps() -> None:
    camera = FakeCamera([_frame(), _frame()])

    frames, fps = run_camera_loop(
        camera,
        pipeline=_pipeline(),
        window_name="test",
        show_window=False,
        max_frames=2,
    )

    assert frames == 2
    assert fps > 0


@pytest.mark.parametrize("quit_key", [ESC_KEY, QUIT_KEY])
def test_loop_calls_callbacks_and_stops_on_quit_key(
    monkeypatch: pytest.MonkeyPatch,
    quit_key: int,
) -> None:
    keys = iter([TOGGLE_KEY, quit_key])
    shown: list[str] = []
    contexts: list[FrameContext] = []
    pressed: list[int] = []
    monkeypatch.setattr(cv2, "imshow", lambda name, _data: shown.append(name))
    monkeypatch.setattr(cv2, "waitKey", lambda _delay: next(keys))

    frames, _ = run_camera_loop(
        FakeCamera([_frame(), _frame(), _frame()]),
        pipeline=_pipeline(),
        window_name="test",
        show_window=True,
        max_frames=0,
        callbacks=RuntimeCallbacks(on_context=contexts.append, on_key=pressed.append),
    )

    assert frames == 2
    assert len(contexts) == 2
    assert pressed == [TOGGLE_KEY, quit_key]
    assert shown == ["test", "test"]


def test_loop_reports_progress_at_interval() -> None:
    progress: list[tuple[int, float]] = []
    camera = FakeCamera([_frame() for _ in range(FPS_LOG_INTERVAL)])

    frames, _ = run_camera_loop(
        camera,
        pipeline=_pipeline(),
        window_name="test",
        show_window=False,
        max_frames=FPS_LOG_INTERVAL,
        callbacks=RuntimeCallbacks(
            on_progress=lambda count, fps: progress.append((count, fps)),
        ),
    )

    assert frames == FPS_LOG_INTERVAL
    assert len(progress) == 1
    count, fps = progress[0]
    assert count == FPS_LOG_INTERVAL
    assert fps > 0


def test_loop_raises_camera_error_after_consecutive_failures() -> None:
    camera = FakeCamera([None] * MAX_CONSECUTIVE_READ_FAILURES)

    with pytest.raises(CameraError, match="fotogramas"):
        run_camera_loop(
            camera,
            pipeline=_pipeline(),
            window_name="test",
            show_window=False,
            max_frames=0,
        )

    assert camera.read_calls == MAX_CONSECUTIVE_READ_FAILURES


def test_interleaved_none_reads_reset_failure_counter() -> None:
    reset_after = MAX_CONSECUTIVE_READ_FAILURES - 1
    reads: list[Frame | None] = (
        [None] * reset_after + [_frame(1.0)] + [None] * reset_after + [_frame(2.0)]
    )
    camera = FakeCamera(reads)

    frames, _ = run_camera_loop(
        camera,
        pipeline=_pipeline(),
        window_name="test",
        show_window=False,
        max_frames=2,
    )

    assert frames == 2
