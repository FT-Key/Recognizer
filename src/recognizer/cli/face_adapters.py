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
from recognizer.core.domain.identity import Role
from recognizer.core.errors import ConfigError

if TYPE_CHECKING:
    from recognizer.adapters.file_access_log_repository import FileAccessLogRepository
    from recognizer.adapters.file_face_repository import FileFaceRepository
    from recognizer.core.ports.face_repository import FaceRepository
    from recognizer.core.ports.identity_provider import IdentityProvider

LOGGER = logging.getLogger("recognizer.menu.face.adapters")


def allowed_roles(*, is_first: bool, role: Role) -> tuple[Role, ...]:
    """Roles enrolables segun el almacen y el rol del operador actual.

    El primer rostro del almacen solo puede ser admin; despues un admin enrola
    cualquier rol, un operator solo operator/viewer y el resto no puede.
    """
    if is_first:
        return (Role.ADMIN,)
    match role:
        case Role.ADMIN:
            return (Role.ADMIN, Role.OPERATOR, Role.VIEWER)
        case Role.OPERATOR:
            return (Role.OPERATOR, Role.VIEWER)
        case _:
            return ()


def default_enroll_role(
    request: AppRunRequest,
    allowed: tuple[Role, ...],
    *,
    logger: logging.Logger = LOGGER,
) -> Role:
    """Rol preseleccionado al enrolar: el de config si esta permitido.

    Evita que un admin quede seleccionado por defecto (el nuevo usuario saldria
    admin); se usa ``face_auth.default_role`` (operator) salvo que no se permita.

    Raises:
        ConfigError: si ``allowed`` esta vacio (no hay rol que preseleccionar).
    """
    if not allowed:
        msg = "Sin roles enrolables para el operador actual."
        raise ConfigError(msg)
    config = load_face_config(request, logger=logger)
    if config is not None and config.default_role in allowed:
        return config.default_role
    return allowed[0]


def store_is_empty(provider: IdentityProvider) -> bool:
    """Indica si el almacen facial esta vacio (primer rostro = admin).

    Solo aplica al proveedor de archivos; cualquier otro proveedor o error se
    trata como "no vacio" para no forzar el rol admin por accidente.
    """
    from recognizer.adapters.file_face_repository import FileFaceRepository
    from recognizer.adapters.file_identity_provider import FileIdentityProvider
    from recognizer.core.errors import RecognizerError

    if not isinstance(provider, FileIdentityProvider):
        return False
    try:
        repository = FileFaceRepository(provider.store_dir)
    except (OSError, RecognizerError):
        return False
    try:
        return len(repository.list_all()) == 0
    except (OSError, RecognizerError):
        return False


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
