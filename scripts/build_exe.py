"""Empaqueta Recognizer (escritorio) como aplicacion de Windows con PyInstaller.

Uso:
    uv run python scripts/build_exe.py

Genera la carpeta de distribucion ``dist/Recognizer/`` con:
    Recognizer.exe        ejecutable principal
    config.yaml           configuracion editable
    models/               modelos MediaPipe editables
    scripts/actions/      scripts de usuario editables
    _internal/            dependencias (Python, DLLs, mediapipe) — no tocar

El usuario final solo descomprime la carpeta y ejecuta Recognizer.exe.
"""

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = PROJECT_ROOT / "packaging" / "recognizer.spec"
DIST_DIR = PROJECT_ROOT / "dist"
PACKAGE_DIR = DIST_DIR / "Recognizer"
EXE_NAME = "Recognizer.exe"

EDITABLE_RESOURCES = ("config.yaml", "models", "scripts/actions")
MODELS_DIR = PROJECT_ROOT / "models"
DOWNLOAD_HINT = "uv run python scripts/download_models.py"


def _validate_inputs() -> None:
    """Comprueba que existan config.yaml y los modelos antes de empaquetar."""
    if not (PROJECT_ROOT / "config.yaml").is_file():
        raise SystemExit("No existe config.yaml en la raiz del proyecto.")
    if not MODELS_DIR.is_dir() or not any(MODELS_DIR.glob("*.task")):
        raise SystemExit(f"Faltan los modelos en {MODELS_DIR}. Ejecuta: {DOWNLOAD_HINT}")


def _run_pyinstaller() -> None:
    """Ejecuta PyInstaller con la spec del proyecto."""
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        str(SPEC_PATH),
    ]
    print(f"Ejecutando: {' '.join(command)}")
    # Herramientas del propio entorno: entradas fijas, no del usuario.
    result = subprocess.run(command, cwd=PROJECT_ROOT, check=False)  # noqa: S603
    if result.returncode != 0:
        raise SystemExit(f"PyInstaller fallo con codigo {result.returncode}")


def _copy_resource(relative: str) -> None:
    """Copia un recurso editable junto al ejecutable dentro de la distribucion."""
    source = PROJECT_ROOT / relative
    target = PACKAGE_DIR / relative
    if not source.exists():
        print(f"Aviso: no existe {relative}, se omite.")
        return
    if source.is_dir():
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _stage_distribution() -> None:
    """Copia los recursos editables junto al ejecutable."""
    if not (PACKAGE_DIR / EXE_NAME).is_file():
        raise SystemExit(f"No se genero el ejecutable esperado: {PACKAGE_DIR / EXE_NAME}")

    for relative in EDITABLE_RESOURCES:
        _copy_resource(relative)


def main() -> int:
    """Empaqueta y prepara la carpeta de distribucion."""
    _validate_inputs()
    _run_pyinstaller()
    _stage_distribution()
    print(f"\nListo. Distribucion en: {PACKAGE_DIR}")
    print(f"Ejecutable: {PACKAGE_DIR / EXE_NAME}")
    print("Comprime la carpeta dist/Recognizer/ para distribuirla.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
