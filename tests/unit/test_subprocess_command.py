"""Tests del adaptador de comandos con un popen inyectado."""

import subprocess
from collections.abc import Sequence

import pytest

from recognizer.adapters.subprocess_command import SubprocessCommandRunner
from recognizer.core.errors import ActionError

EXPECTED_ARGV = ["notepad.exe", "archivo con espacios.txt"]


class RecordingPopen:
    """Doble de popen que acumula los argv recibidos."""

    def __init__(self) -> None:
        self.argvs: list[tuple[str, ...]] = []

    def __call__(self, argv: Sequence[str]) -> object:
        self.argvs.append(tuple(argv))
        return object()


def test_run_delegates_to_injected_popen() -> None:
    popen = RecordingPopen()
    runner = SubprocessCommandRunner(popen=popen)

    runner.run(EXPECTED_ARGV)

    assert popen.argvs == [tuple(EXPECTED_ARGV)]


def test_os_error_becomes_action_error() -> None:
    def failing_popen(argv: Sequence[str]) -> object:
        del argv
        msg = "comando no encontrado"
        raise OSError(msg)

    runner = SubprocessCommandRunner(popen=failing_popen)

    with pytest.raises(ActionError, match="No se pudo ejecutar"):
        runner.run(["comando-inexistente"])


def test_default_popen_uses_list_and_disables_shell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_popen(argv: list[str], **kwargs: object) -> object:
        calls.append((argv, kwargs))
        return object()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    runner = SubprocessCommandRunner()

    runner.run(EXPECTED_ARGV)

    assert len(calls) == 1
    argv, kwargs = calls[0]
    assert argv == EXPECTED_ARGV
    assert isinstance(argv, list)
    assert kwargs["shell"] is False
    assert kwargs["close_fds"] is True
    assert kwargs["stdout"] is subprocess.DEVNULL
    assert kwargs["stderr"] is subprocess.DEVNULL
