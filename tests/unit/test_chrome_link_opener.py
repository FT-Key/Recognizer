"""Tests del adaptador ChromeLinkOpener con popen y autodeteccion doblados."""

import subprocess
from collections.abc import Sequence

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
    monkeypatch.setattr(chrome_link_opener, "autodetect_chrome", lambda: None)
    opener = ChromeLinkOpener(popen=RecordingPopen())

    with pytest.raises(ActionError, match="No se encontro Chrome"):
        opener.open(URL)


def test_autodetect_returns_none_without_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chrome_link_opener, "autodetect_browser", lambda **_kw: None)

    assert chrome_link_opener.autodetect_chrome() is None


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
