"""Tests del adaptador ChromeLinkOpener con popen y autodeteccion doblados."""

import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from recognizer.adapters import chrome_link_opener
from recognizer.adapters.chrome_link_opener import ChromeLinkOpener
from recognizer.core.errors import ActionError

CHROME_EXECUTABLE = "C:\\chrome.exe"
URL = "https://x.example"


class RecordingPopen:
    """Doble de popen que acumula los argv recibidos."""

    def __init__(self) -> None:
        self.argvs: list[tuple[str, ...]] = []

    def __call__(self, argv: Sequence[str]) -> object:
        self.argvs.append(tuple(argv))
        return object()


def test_open_delegates_to_injected_popen_with_exact_argv() -> None:
    popen = RecordingPopen()
    opener = ChromeLinkOpener(executable=CHROME_EXECUTABLE, popen=popen)

    opener.open(URL)

    assert popen.argvs == [(CHROME_EXECUTABLE, URL)]


def test_os_error_in_popen_becomes_action_error() -> None:
    def failing_popen(argv: Sequence[str]) -> object:
        del argv
        msg = "no se pudo lanzar"
        raise OSError(msg)

    opener = ChromeLinkOpener(executable=CHROME_EXECUTABLE, popen=failing_popen)

    with pytest.raises(ActionError, match="No se pudo abrir el enlace"):
        opener.open(URL)


def test_autodetect_failure_raises_action_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chrome_link_opener, "_autodetect_chrome", lambda: None)
    opener = ChromeLinkOpener(popen=RecordingPopen())

    with pytest.raises(ActionError, match="No se encontro Chrome"):
        opener.open(URL)


def test_autodetect_prefers_command_found_in_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: CHROME_EXECUTABLE)

    assert chrome_link_opener._autodetect_chrome() == CHROME_EXECUTABLE


def test_autodetect_falls_back_to_common_install_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    monkeypatch.setenv("PROGRAMFILES", "C:\\Program Files")
    monkeypatch.delenv("PROGRAMFILES(X86)", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(Path, "is_file", lambda _self: True)

    detected = chrome_link_opener._autodetect_chrome()

    expected = str(Path("C:\\Program Files") / chrome_link_opener.CHROME_RELATIVE_PATH)
    assert detected == expected


def test_autodetect_returns_none_without_chrome(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    for env_var in chrome_link_opener.CHROME_ENV_ROOTS:
        monkeypatch.delenv(env_var, raising=False)

    assert chrome_link_opener._autodetect_chrome() is None


def test_default_popen_uses_list_and_disables_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_popen(argv: list[str], **kwargs: object) -> object:
        calls.append((argv, kwargs))
        return object()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    opener = ChromeLinkOpener(executable=CHROME_EXECUTABLE)

    opener.open(URL)

    assert len(calls) == 1
    argv, kwargs = calls[0]
    assert argv == [CHROME_EXECUTABLE, URL]
    assert isinstance(argv, list)
    assert kwargs["shell"] is False
    assert kwargs["close_fds"] is True
    assert kwargs["stdout"] is subprocess.DEVNULL
    assert kwargs["stderr"] is subprocess.DEVNULL
