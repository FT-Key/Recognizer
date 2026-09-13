"""Carga de configuracion desde YAML.

Vive fuera del nucleo porque el acceso a archivos es infraestructura.
"""

from pathlib import Path

import yaml
from pydantic import ValidationError

from recognizer.core.config import AppConfig
from recognizer.core.errors import ConfigError


def load_config(path: Path) -> AppConfig:
    """Carga y valida la configuracion desde un archivo YAML.

    Raises:
        ConfigError: si el archivo no existe, el YAML es invalido o los
            valores no cumplen el esquema.
    """
    if not path.is_file():
        msg = f"No existe el archivo de configuracion: {path}"
        raise ConfigError(msg)

    try:
        raw: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        msg = f"YAML invalido en {path}"
        raise ConfigError(msg) from exc

    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        msg = f"La configuracion raiz debe ser un objeto YAML en {path}"
        raise ConfigError(msg)

    try:
        return AppConfig.model_validate(raw)
    except ValidationError as exc:
        msg = f"Configuracion invalida en {path}: {exc}"
        raise ConfigError(msg) from exc
