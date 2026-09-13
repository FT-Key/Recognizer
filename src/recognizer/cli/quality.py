"""Comandos del gate de calidad, invocables con `uv run <comando>`."""

import subprocess
import sys
from collections.abc import Sequence


def _run(command: Sequence[str]) -> int:
    # Herramientas del propio entorno virtual: entradas fijas, no del usuario.
    return subprocess.call(command)  # noqa: S603


def lint() -> int:
    """Ejecuta ruff check y la verificacion de formato."""
    check = _run(["ruff", "check", "."])
    format_check = _run(["ruff", "format", "--check", "."])
    return check or format_check


def typecheck() -> int:
    """Ejecuta mypy en modo estricto."""
    return _run(["mypy"])


def test() -> int:
    """Ejecuta pytest con cobertura."""
    return _run(["pytest"])


def check_arch() -> int:
    """Verifica los contratos de arquitectura con import-linter."""
    return _run(["lint-imports"])


if __name__ == "__main__":
    sys.exit(check_arch())
