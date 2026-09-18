"""Resolucion de rutas y modo de ejecucion, sin dependencias de vision.

Vive aparte de `cli/app.py` para que el menu pueda arrancar sin importar
`cv2`/`mediapipe`: abrir el launcher no debe cargar librerias pesadas.
"""

import os
import sys
import tempfile
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("config.yaml")
# En el .exe (frozen) el servidor de salud arranca por defecto para que la web
# detecte la app; en desarrollo queda desactivado (0) para no abrir puertos.
DEFAULT_HEALTH_PORT_FROZEN = 8765
DEFAULT_HEALTH_PORT_SOURCE = 0
LOGS_DIRNAME = "logs"
LOG_FILENAME = "recognizer.log"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def is_frozen() -> bool:
    """Indica si corremos dentro de un ejecutable empaquetado (PyInstaller)."""
    return bool(getattr(sys, "frozen", False))


def default_config_path() -> Path:
    """Resuelve config.yaml junto al ejecutable cuando esta empaquetado."""
    if is_frozen():
        return Path(sys.executable).parent / DEFAULT_CONFIG_PATH
    return DEFAULT_CONFIG_PATH


def default_health_port() -> int:
    """Puerto de salud por defecto segun el modo de ejecucion."""
    return DEFAULT_HEALTH_PORT_FROZEN if is_frozen() else DEFAULT_HEALTH_PORT_SOURCE


def default_log_file() -> Path | None:
    """Ruta del log por defecto: junto al .exe si esta empaquetado, si no ninguno."""
    if is_frozen():
        return Path(sys.executable).parent / LOGS_DIRNAME / LOG_FILENAME
    return None


def resolve_log_file(log_file: Path) -> Path:
    """Resuelve la ruta del log y garantiza que su carpeta exista.

    Si la carpeta junto al ejecutable no es escribible (p. ej. Program Files),
    cae al directorio temporal del sistema para no perder el diagnostico.
    """
    candidate = log_file if log_file.is_absolute() else Path.cwd() / log_file
    try:
        candidate.parent.mkdir(parents=True, exist_ok=True)
        return candidate
    except OSError:
        fallback = Path(tempfile.gettempdir()) / LOGS_DIRNAME / LOG_FILENAME
        fallback.parent.mkdir(parents=True, exist_ok=True)
        return fallback


def prepare_workspace(config_arg: Path) -> Path:
    """Resuelve la ruta de config y fija el CWD para rutas relativas del YAML.

    Cuando la app corre empaquetada, los recursos (config.yaml y models/) viven
    junto al ejecutable; cambiar el CWD alli hace que ``models/*.task`` del YAML
    se resuelvan sin tocar la configuracion.
    """
    base_dir = Path(sys.executable).parent if is_frozen() else Path.cwd()
    config_path = config_arg if config_arg.is_absolute() else base_dir / config_arg
    if config_path.parent != Path.cwd():
        os.chdir(config_path.parent)
    return config_path
