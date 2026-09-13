"""Adaptador de ejecucion de scripts locales con subprocess."""

import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

from recognizer.core.domain.action import ScriptInterpreter, ScriptRequest
from recognizer.core.errors import ActionError
from recognizer.core.ports.script_runner import ScriptRunner

PYTHON_EXTENSION = ".py"
POWERSHELL_EXTENSION = ".ps1"
BATCH_EXTENSION = ".bat"
CMD_EXTENSION = ".cmd"
BASH_EXTENSION = ".sh"

POWERSHELL_EXECUTABLE = "powershell"
POWERSHELL_NO_PROFILE_FLAG = "-NoProfile"
POWERSHELL_EXECUTION_POLICY_FLAG = "-ExecutionPolicy"
POWERSHELL_BYPASS_POLICY = "Bypass"
POWERSHELL_FILE_FLAG = "-File"
CMD_EXECUTABLE = "cmd"
CMD_RUN_FLAG = "/c"
BASH_EXECUTABLE = "bash"

_EXTENSION_INTERPRETERS: Mapping[str, ScriptInterpreter] = {
    PYTHON_EXTENSION: ScriptInterpreter.PYTHON,
    POWERSHELL_EXTENSION: ScriptInterpreter.POWERSHELL,
    BATCH_EXTENSION: ScriptInterpreter.CMD,
    CMD_EXTENSION: ScriptInterpreter.CMD,
    BASH_EXTENSION: ScriptInterpreter.BASH,
}


def _resolve_interpreter(request: ScriptRequest) -> ScriptInterpreter:
    if request.interpreter is not ScriptInterpreter.AUTO:
        return request.interpreter
    suffix = Path(request.path).suffix.lower()
    return _EXTENSION_INTERPRETERS.get(suffix, ScriptInterpreter.DIRECT)


def _build_argv(request: ScriptRequest, interpreter: ScriptInterpreter) -> tuple[str, ...]:
    match interpreter:
        case ScriptInterpreter.PYTHON:
            return (sys.executable, request.path, *request.args)
        case ScriptInterpreter.POWERSHELL:
            return (
                POWERSHELL_EXECUTABLE,
                POWERSHELL_NO_PROFILE_FLAG,
                POWERSHELL_EXECUTION_POLICY_FLAG,
                POWERSHELL_BYPASS_POLICY,
                POWERSHELL_FILE_FLAG,
                request.path,
                *request.args,
            )
        case ScriptInterpreter.CMD:
            return (CMD_EXECUTABLE, CMD_RUN_FLAG, request.path, *request.args)
        case ScriptInterpreter.BASH:
            return (BASH_EXECUTABLE, request.path, *request.args)
        case _:
            return (request.path, *request.args)


def _build_env(request: ScriptRequest) -> Mapping[str, str] | None:
    if request.env is None:
        return None
    return {**os.environ, **request.env}


def _resolve_timeout(request: ScriptRequest) -> float | None:
    return request.timeout_seconds if request.timeout_seconds > 0 else None


def _default_popen(
    argv: tuple[str, ...],
    *,
    cwd: str | None,
    env: Mapping[str, str] | None,
) -> object:
    # argv viene de config.yaml (confiable): shell desactivado a proposito.
    return subprocess.Popen(  # noqa: S603
        list(argv),
        shell=False,
        close_fds=True,
        cwd=cwd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _default_run(
    argv: tuple[str, ...],
    *,
    cwd: str | None,
    env: Mapping[str, str] | None,
    timeout: float | None,
) -> object:
    # argv viene de config.yaml (confiable): shell desactivado a proposito.
    return subprocess.run(  # noqa: S603
        list(argv),
        shell=False,
        cwd=cwd,
        env=env,
        timeout=timeout,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class SubprocessScriptRunner(ScriptRunner):
    """Ejecuta scripts locales en segundo plano o esperando su fin."""

    def __init__(
        self,
        *,
        popen: Callable[..., object] | None = None,
        run: Callable[..., object] | None = None,
    ) -> None:
        self._popen = popen or _default_popen
        self._run = run or _default_run

    def run(self, request: ScriptRequest) -> None:
        """Ejecuta el script descrito por request.

        Raises:
            ActionError: si el sistema no puede lanzar el script o si el modo
                bloqueante excede su timeout.
        """
        interpreter = _resolve_interpreter(request)
        argv = _build_argv(request, interpreter)
        env = _build_env(request)
        if request.blocking:
            self._run_blocking(request=request, argv=argv, env=env)
        else:
            self._run_background(request=request, argv=argv, env=env)

    def _run_background(
        self,
        *,
        request: ScriptRequest,
        argv: tuple[str, ...],
        env: Mapping[str, str] | None,
    ) -> None:
        try:
            self._popen(argv, cwd=request.working_dir, env=env)
        except OSError as exc:
            msg = f"No se pudo ejecutar el script: {request.path}"
            raise ActionError(msg) from exc

    def _run_blocking(
        self,
        *,
        request: ScriptRequest,
        argv: tuple[str, ...],
        env: Mapping[str, str] | None,
    ) -> None:
        try:
            self._run(
                argv,
                cwd=request.working_dir,
                env=env,
                timeout=_resolve_timeout(request),
            )
        except subprocess.TimeoutExpired as exc:
            msg = f"El script excedio el tiempo limite ({request.timeout_seconds}s): {request.path}"
            raise ActionError(msg) from exc
        except OSError as exc:
            msg = f"No se pudo ejecutar el script: {request.path}"
            raise ActionError(msg) from exc
