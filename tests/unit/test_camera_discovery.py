"""Tests del descubrimiento de camaras, sin hardware ni cv2 real.

El adaptador importa ``cv2`` dentro del metodo, asi que los tests inyectan
un modulo falso en ``sys.modules["cv2"]`` (nunca ``import cv2`` aqui).
Lo que abra camara real va marcado como ``integration`` (excluido del gate).
"""

from __future__ import annotations

import sys
import types
from dataclasses import FrozenInstanceError

import pytest

from recognizer.adapters.camera_discovery import (
    CAMERA_LABEL_TEMPLATE,
    OpenCVCameraEnumerator,
)
from recognizer.core.domain.camera import CameraInfo


class FakeCapture:
    """Doble de cv2.VideoCapture con resultado programable."""

    def __init__(self, *, opened: bool, ok: bool, frame: object | None) -> None:
        self._opened = opened
        self._ok = ok
        self._frame = frame
        self.release_calls = 0

    def isOpened(self) -> bool:
        return self._opened

    def read(self) -> tuple[bool, object | None]:
        return (self._ok, self._frame)

    def release(self) -> None:
        self.release_calls += 1


def _install_fake_cv2(
    monkeypatch: pytest.MonkeyPatch, captures: dict[int, FakeCapture]
) -> dict[int, FakeCapture]:
    """Inyecta un cv2 falso que entrega las capturas por indice."""
    seen: list[int] = []

    def fake_video_capture(index: int) -> FakeCapture:
        seen.append(index)
        capture = captures.get(index)
        if capture is None:
            return FakeCapture(opened=False, ok=False, frame=None)
        return capture

    module = types.ModuleType("cv2")
    module.VideoCapture = fake_video_capture  # type: ignore[attr-defined]
    module.__seen__ = seen  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "cv2", module)
    return captures


def test_rejects_negative_max_index() -> None:
    with pytest.raises(ValueError, match="max_index"):
        OpenCVCameraEnumerator(max_index=-1)


def test_returns_only_cameras_with_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    captures = {
        0: FakeCapture(opened=True, ok=True, frame=object()),
        1: FakeCapture(opened=False, ok=False, frame=None),
        2: FakeCapture(opened=True, ok=False, frame=None),
        3: FakeCapture(opened=True, ok=True, frame=None),
    }
    _install_fake_cv2(monkeypatch, captures)

    result = OpenCVCameraEnumerator(max_index=3).list_cameras()

    assert result == (CameraInfo(index=0, label=CAMERA_LABEL_TEMPLATE.format(index=0)),)
    for capture in captures.values():
        assert capture.release_calls == 1


def test_empty_when_no_camera_delivers_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_cv2(monkeypatch, {})

    assert OpenCVCameraEnumerator(max_index=2).list_cameras() == ()


def test_respects_max_index_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    captures = {
        0: FakeCapture(opened=True, ok=True, frame=object()),
        1: FakeCapture(opened=True, ok=True, frame=object()),
    }
    _install_fake_cv2(monkeypatch, captures)

    result = OpenCVCameraEnumerator(max_index=0).list_cameras()

    assert [info.index for info in result] == [0]


def test_camera_info_is_frozen_value() -> None:
    info = CameraInfo(index=2, label="Cámara 2")
    assert info == CameraInfo(index=2, label="Cámara 2")
    with pytest.raises(FrozenInstanceError, match="index"):
        info.index = 5  # type: ignore[misc]


@pytest.mark.integration
def test_list_cameras_with_real_hardware() -> None:
    """Abre la camara real; solo corre con ``-m integration``."""
    result = OpenCVCameraEnumerator(max_index=0).list_cameras()
    assert isinstance(result, tuple)
