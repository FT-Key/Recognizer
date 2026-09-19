"""Fabricas perezosas de adaptadores faciales para la GUI (imperative shell).

Construye config, repositorios y proveedor de identidad desde
``request.config_path`` sin cargar modelos de vision (solo stdlib + pydantic).
El submenu facial y los paneles de usuarios/accesos las usan por defecto y los
tests inyectan sus propios dobles.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from recognizer.core.config import FaceAuthConfig
from recognizer.core.domain.app import AppRunRequest

if TYPE_CHECKING:
    from recognizer.adapters.file_access_log_repository import FileAccessLogRepository
    from recognizer.adapters.file_face_repository import FileFaceRepository
    from recognizer.core.ports.face_repository import FaceRepository
    from recognizer.core.ports.identity_provider import IdentityProvider

LOGGER = logging.getLogger("recognizer.menu.face.adapters")


def load_face_config(
    request: AppRunRequest, *, logger: logging.Logger = LOGGER
) -> FaceAuthConfig | None:
    """Config facial desde ``request.config_path`` o ``None`` si no se pudo cargar."""
    from recognizer.core.errors import ConfigError
    from recognizer.settings import load_config

    try:
        return load_config(request.config_path).face_auth
    except ConfigError as exc:
        logger.warning("Sin config facial (%s); panel sin datos.", exc)
        return None


def default_face_repository(
    request: AppRunRequest, *, logger: logging.Logger = LOGGER
) -> FileFaceRepository | None:
    """Almacen de rostros sobre el directorio de la config, o ``None`` si falla."""
    from recognizer.adapters.file_face_repository import FileFaceRepository
    from recognizer.core.errors import RecognizerError

    config = load_face_config(request, logger=logger)
    if config is None:
        return None
    try:
        return FileFaceRepository(config.store_dir)
    except (OSError, RecognizerError) as exc:
        logger.warning("Almacen facial no disponible (%s).", exc)
        return None


def default_access_repository(
    request: AppRunRequest, *, logger: logging.Logger = LOGGER
) -> FileAccessLogRepository | None:
    """Registro de accesos sobre el directorio de la config, o ``None`` si falla."""
    from recognizer.adapters.file_access_log_repository import FileAccessLogRepository
    from recognizer.core.errors import RecognizerError

    config = load_face_config(request, logger=logger)
    if config is None:
        return None
    try:
        return FileAccessLogRepository(config.access_dir)
    except (OSError, RecognizerError) as exc:
        logger.warning("Registro de accesos no disponible (%s).", exc)
        return None


def default_identity_provider(
    request: AppRunRequest,
    *,
    logger: logging.Logger = LOGGER,
    repository: FaceRepository | None = None,
) -> IdentityProvider:
    """Proveedor de sesion liviano; invitado con acceso total si no hay config.

    ``repository`` es inyectable (mismo almacen que el panel); si no se pasa, se
    construye uno sobre ``face_auth.store_dir``. Nunca carga modelos de vision.
    """
    from recognizer.adapters.file_face_repository import FileFaceRepository
    from recognizer.adapters.file_identity_provider import (
        AllowAllIdentityProvider,
        FileIdentityProvider,
    )
    from recognizer.core.errors import RecognizerError

    config = load_face_config(request, logger=logger)
    if config is None:
        return AllowAllIdentityProvider()
    repo = repository
    if repo is None:
        try:
            repo = FileFaceRepository(config.store_dir)
        except (OSError, RecognizerError) as exc:
            logger.warning("Almacen facial no disponible (%s); sesion invitada.", exc)
            return AllowAllIdentityProvider()
    return FileIdentityProvider(
        config.store_dir,
        repo,
        session_timeout_seconds=config.session_timeout_seconds,
    )
