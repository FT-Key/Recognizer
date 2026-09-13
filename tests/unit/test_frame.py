"""Tests del objeto de valor Frame."""

import numpy as np
import pytest
from numpy.typing import NDArray

from recognizer.core.domain.frame import Frame


def _make_frame() -> Frame:
    data: NDArray[np.uint8] = np.zeros((4, 6, 3), dtype=np.uint8)
    return Frame(data=data, timestamp=1.0)


def test_width_and_height_reflect_shape() -> None:
    frame = _make_frame()
    assert frame.width == 6
    assert frame.height == 4


def test_frame_is_immutable() -> None:
    frame = _make_frame()
    with pytest.raises(AttributeError):
        frame.__setattr__("timestamp", 2.0)
