"""Tests de la codificacion PNG en memoria (numpy sintetico), sin hardware."""

import cv2
import numpy as np
import pytest

from recognizer.adapters.image_codec import encode_png
from recognizer.core.errors import ImageEncodingError

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
FRAME_SHAPE = (8, 8, 3)


def _bgr_frame() -> np.ndarray:
    return np.zeros(FRAME_SHAPE, dtype=np.uint8)


def test_encode_png_returns_png_bytes() -> None:
    encoded = encode_png(_bgr_frame())

    assert isinstance(encoded, bytes)
    assert encoded.startswith(PNG_MAGIC)


def test_encode_png_output_is_decodable() -> None:
    encoded = encode_png(_bgr_frame())

    decoded = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR)

    assert decoded is not None
    assert decoded.shape == FRAME_SHAPE


def test_encode_png_raises_when_opencv_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("cv2.imencode", lambda *_args, **_kwargs: (False, None))

    with pytest.raises(ImageEncodingError, match="PNG"):
        encode_png(_bgr_frame())


def test_encode_png_wraps_cv2_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_args: object, **_kwargs: object) -> object:
        raise cv2.error("codificador roto")

    monkeypatch.setattr("cv2.imencode", _boom)

    with pytest.raises(ImageEncodingError, match="PNG"):
        encode_png(_bgr_frame())
