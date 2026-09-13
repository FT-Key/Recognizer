"""Tests del CLI de smoke sin camara real (doble verificacion previa a side effects)."""

from pathlib import Path

import pytest

from recognizer.cli import smoke

EXPECTED_FAILURE_CODE = 1


def test_main_without_window_and_default_frames_fails_before_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(path: Path) -> object:
        del path
        msg = "load_config no debe llamarse sin --frames."
        raise AssertionError(msg)

    class FailingCamera:
        """Doble que falla si el smoke intenta abrir la camara."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs
            msg = "La camara no debe abrirse sin --frames."
            raise AssertionError(msg)

    monkeypatch.setattr(smoke, "load_config", fail_if_called)
    monkeypatch.setattr(smoke, "OpenCVCamera", FailingCamera)

    assert smoke.main(["--no-window"]) == EXPECTED_FAILURE_CODE
