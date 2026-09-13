"""Tests del adaptador de scripts con dobles de popen/run inyectados."""

import os
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass

import pytest

from recognizer.adapters.subprocess_script import SubprocessScriptRunner
from recognizer.core.domain.action import ScriptInterpreter, ScriptRequest
from recognizer.core.errors import ActionError

ARGS = ("--flag", "valor")
WORKING_DIR = "C:/scripts"


@dataclass(frozen=True, slots=True)
class PopenCall:
    """Llamada capturada al doble de popen."""

    argv: tuple[str, ...]
    cwd: str | None
    env: Mapping[str, str] | None


@dataclass(frozen=True, slots=True)
class RunCall:
    """Llamada capturada al doble de run."""

    argv: tuple[str, ...]
    cwd: str | None
    env: Mapping[str, str] | None
    timeout: float | None


class RecordingPopen:
    """Doble de popen que acumula las llamadas recibidas."""

    def __init__(self) -> None:
        self.calls: list[PopenCall] = []

    def __call__(
        self,
        argv: tuple[str, ...],
        *,
        cwd: str | None,
        env: Mapping[str, str] | None,
    ) -> object:
        self.calls.append(PopenCall(argv=tuple(argv), cwd=cwd, env=env))
        return object()


class RecordingRun:
    """Doble de run que acumula las llamadas recibidas."""

    def __init__(self) -> None:
        self.calls: list[RunCall] = []

    def __call__(
        self,
        argv: tuple[str, ...],
        *,
        cwd: str | None,
        env: Mapping[str, str] | None,
        timeout: float | None,
    ) -> object:
        self.calls.append(RunCall(argv=tuple(argv), cwd=cwd, env=env, timeout=timeout))
        return object()


def _request(
    path: str,
    *,
    args: tuple[str, ...] = ARGS,
    interpreter: ScriptInterpreter = ScriptInterpreter.AUTO,
    working_dir: str | None = None,
    blocking: bool = False,
    timeout_seconds: float = 0.0,
    env: Mapping[str, str] | None = None,
) -> ScriptRequest:
    return ScriptRequest(
        path=path,
        args=args,
        interpreter=interpreter,
        working_dir=working_dir,
        blocking=blocking,
        timeout_seconds=timeout_seconds,
        env=env,
    )


@pytest.mark.parametrize(
    ("path", "prefix"),
    [
        ("script.py", (sys.executable,)),
        ("SCRIPT.PY", (sys.executable,)),
        (
            "script.ps1",
            ("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"),
        ),
        (
            "script.PS1",
            ("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"),
        ),
        ("script.bat", ("cmd", "/c")),
        ("script.BAT", ("cmd", "/c")),
        ("script.cmd", ("cmd", "/c")),
        ("script.CMD", ("cmd", "/c")),
        ("script.sh", ("bash",)),
        ("script.SH", ("bash",)),
        ("script.unknown", ()),
        ("sin_extension", ()),
    ],
)
def test_auto_interpreter_resolves_by_extension_case_insensitive(
    path: str,
    prefix: tuple[str, ...],
) -> None:
    popen = RecordingPopen()
    runner = SubprocessScriptRunner(popen=popen)

    runner.run(_request(path))

    assert popen.calls[0].argv == (*prefix, path, *ARGS)


def test_explicit_interpreter_has_priority_over_extension() -> None:
    popen = RecordingPopen()
    runner = SubprocessScriptRunner(popen=popen)

    runner.run(_request("notas.txt", interpreter=ScriptInterpreter.PYTHON))

    assert popen.calls[0].argv == (sys.executable, "notas.txt", *ARGS)


def test_blocking_false_uses_popen_and_not_run() -> None:
    popen = RecordingPopen()
    run = RecordingRun()
    runner = SubprocessScriptRunner(popen=popen, run=run)

    runner.run(_request("script.sh", blocking=False))

    assert len(popen.calls) == 1
    assert run.calls == []


def test_blocking_true_uses_run_and_not_popen() -> None:
    popen = RecordingPopen()
    run = RecordingRun()
    runner = SubprocessScriptRunner(popen=popen, run=run)

    runner.run(_request("script.sh", blocking=True))

    assert len(run.calls) == 1
    assert popen.calls == []


def test_blocking_passes_positive_timeout() -> None:
    run = RecordingRun()
    runner = SubprocessScriptRunner(run=run)

    runner.run(_request("script.sh", blocking=True, timeout_seconds=2.5))

    assert run.calls[0].timeout == 2.5


@pytest.mark.parametrize("timeout_seconds", [0.0, -1.0])
def test_blocking_passes_none_timeout_when_non_positive(timeout_seconds: float) -> None:
    run = RecordingRun()
    runner = SubprocessScriptRunner(run=run)

    runner.run(_request("script.sh", blocking=True, timeout_seconds=timeout_seconds))

    assert run.calls[0].timeout is None


def test_env_is_merged_over_os_environ() -> None:
    real_key = next(iter(os.environ))
    popen = RecordingPopen()
    runner = SubprocessScriptRunner(popen=popen)

    runner.run(_request("script.sh", env={"RECOGNIZER_GESTURE": "Victory", real_key: "override"}))

    env = popen.calls[0].env
    assert env is not None
    assert env["RECOGNIZER_GESTURE"] == "Victory"
    assert env[real_key] == "override"


def test_env_none_is_forwarded_as_none() -> None:
    popen = RecordingPopen()
    runner = SubprocessScriptRunner(popen=popen)

    runner.run(_request("script.sh", env=None))

    assert popen.calls[0].env is None


def test_working_dir_is_forwarded_to_cwd() -> None:
    popen = RecordingPopen()
    runner = SubprocessScriptRunner(popen=popen)

    runner.run(_request("script.sh", working_dir=WORKING_DIR))

    assert popen.calls[0].cwd == WORKING_DIR


def test_os_error_in_popen_becomes_action_error() -> None:
    def failing_popen(
        argv: tuple[str, ...],
        *,
        cwd: str | None,
        env: Mapping[str, str] | None,
    ) -> object:
        del argv, cwd, env
        msg = "no se pudo lanzar"
        raise OSError(msg)

    runner = SubprocessScriptRunner(popen=failing_popen)

    with pytest.raises(ActionError, match="No se pudo ejecutar"):
        runner.run(_request("script.sh"))


def test_os_error_in_run_becomes_action_error() -> None:
    def failing_run(
        argv: tuple[str, ...],
        *,
        cwd: str | None,
        env: Mapping[str, str] | None,
        timeout: float | None,
    ) -> object:
        del argv, cwd, env, timeout
        msg = "no se pudo lanzar"
        raise OSError(msg)

    runner = SubprocessScriptRunner(run=failing_run)

    with pytest.raises(ActionError, match="No se pudo ejecutar"):
        runner.run(_request("script.sh", blocking=True))


def test_timeout_expired_in_run_becomes_action_error() -> None:
    def timeout_run(
        argv: tuple[str, ...],
        *,
        cwd: str | None,
        env: Mapping[str, str] | None,
        timeout: float | None,
    ) -> object:
        del argv, cwd, env
        raise subprocess.TimeoutExpired(cmd="script.sh", timeout=timeout or 0.0)

    runner = SubprocessScriptRunner(run=timeout_run)

    with pytest.raises(ActionError, match="tiempo limite"):
        runner.run(_request("script.sh", blocking=True, timeout_seconds=1.0))


def test_default_popen_uses_list_and_disables_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_popen(argv: list[str], **kwargs: object) -> object:
        calls.append((argv, kwargs))
        return object()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    runner = SubprocessScriptRunner()

    runner.run(_request("script.cmd"))

    assert len(calls) == 1
    argv, kwargs = calls[0]
    assert argv == ["cmd", "/c", "script.cmd", *ARGS]
    assert isinstance(argv, list)
    assert kwargs["shell"] is False
    assert kwargs["close_fds"] is True
    assert kwargs["stdout"] is subprocess.DEVNULL
    assert kwargs["stderr"] is subprocess.DEVNULL


def test_default_run_uses_list_and_disables_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(argv: list[str], **kwargs: object) -> object:
        calls.append((argv, kwargs))
        return object()

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = SubprocessScriptRunner()

    runner.run(_request("script.sh", blocking=True, timeout_seconds=1.5))

    assert len(calls) == 1
    argv, kwargs = calls[0]
    assert argv == ["bash", "script.sh", *ARGS]
    assert isinstance(argv, list)
    assert kwargs["shell"] is False
    assert kwargs["check"] is False
    assert kwargs["timeout"] == 1.5
    assert kwargs["stdout"] is subprocess.DEVNULL
    assert kwargs["stderr"] is subprocess.DEVNULL
