"""Proveedor de identidad basado en la sesion facial en disco.

Lee ``<store_dir>/session.json`` (``{face_id, authenticated_at, expires_at}``)
escrito por el login facial. Sin sesion, con sesion caducada o con rostro
desconocido devuelve la identidad invitada. Solo usa la biblioteca estandar
(JSON/tiempo), de modo que el menu puede resolver la identidad sin cargar
modelos de vision. El directorio ya se crea con ``0o700`` en el repositorio.
"""

import json
import logging
import os
import tempfile
import time
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from recognizer.core.constants import (
    DEFAULT_SESSION_TIMEOUT_SECONDS,
    LOCAL_IDENTITY_FACE_ID,
    LOCAL_IDENTITY_NAME,
    SESSION_FILENAME,
)
from recognizer.core.domain.face import EnrolledFace
from recognizer.core.domain.identity import (
    Identity,
    Role,
    SessionRecord,
    anonymous_identity,
    session_expired,
)
from recognizer.core.errors import AuthError, FaceRepositoryError
from recognizer.core.ports.face_repository import FaceRepository
from recognizer.core.ports.identity_provider import IdentityProvider

LOGGER = logging.getLogger("recognizer.face_session")

SESSION_FACE_ID_KEY = "face_id"
SESSION_AUTH_AT_KEY = "authenticated_at"
SESSION_EXPIRES_AT_KEY = "expires_at"


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    """Escribe JSON de forma atomica (temporal + rename) en el mismo directorio."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, tmp_name = tempfile.mkstemp(
            dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
        )
    except OSError as exc:
        msg = f"No se pudo escribir {path}."
        raise FaceRepositoryError(msg) from exc
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
        tmp_path.replace(path)
    except OSError as exc:
        with suppress(OSError):
            tmp_path.unlink()
        msg = f"No se pudo escribir {path}."
        raise FaceRepositoryError(msg) from exc


class FileIdentityProvider(IdentityProvider):
    """Resuelve la identidad desde ``session.json`` junto al almacen de rostros."""

    def __init__(
        self,
        store_dir: Path | str,
        repository: FaceRepository,
        *,
        session_timeout_seconds: int = DEFAULT_SESSION_TIMEOUT_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if session_timeout_seconds < 0:
            msg = "La sesion requiere session_timeout_seconds >= 0."
            raise FaceRepositoryError(msg)
        self._store_dir = Path(store_dir)
        self._store_dir.mkdir(parents=True, exist_ok=True)
        with suppress(OSError):
            self._store_dir.chmod(0o700)
        self._repository = repository
        self._timeout_seconds = session_timeout_seconds
        self._clock = clock

    @property
    def store_dir(self) -> Path:
        """Directorio donde vive la sesion junto al almacen de rostros."""
        return self._store_dir

    def _session_path(self) -> Path:
        return self._store_dir / SESSION_FILENAME

    def _now_iso(self) -> str:
        return datetime.fromtimestamp(self._clock(), tz=UTC).isoformat()

    def _read_session(self) -> SessionRecord | None:
        """Sesion persistida o ``None`` si falta o esta corrupta (fail-open a invitado)."""
        path = self._session_path()
        if not path.is_file():
            return None
        try:
            raw = cast(object, json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            LOGGER.warning("Sesion facial ilegible (%s); se usa invitado.", exc)
            return None
        if not isinstance(raw, dict):
            return None
        face_id = raw.get(SESSION_FACE_ID_KEY)
        authenticated_at = raw.get(SESSION_AUTH_AT_KEY, "")
        expires_at = raw.get(SESSION_EXPIRES_AT_KEY, "")
        if not isinstance(face_id, str) or not face_id:
            return None
        if not isinstance(authenticated_at, str) or not isinstance(expires_at, str):
            return None
        return SessionRecord(
            face_id=face_id, authenticated_at=authenticated_at, expires_at=expires_at
        )

    def current_identity(self) -> Identity:
        """Identidad de la sesion vigente o la invitada si no hay login."""
        record = self._read_session()
        if record is None:
            return anonymous_identity()
        face = self._repository.find_by_id(record.face_id)
        if face is None:
            LOGGER.warning("Sesion de rostro desconocido %s; se usa invitado.", record.face_id)
            return anonymous_identity()
        if session_expired(record, now_iso=self._now_iso()):
            return anonymous_identity()
        return Identity(
            face_id=face.face_id,
            name=face.name,
            role=face.role,
            authenticated_at=record.authenticated_at,
        )

    def require_role(self, *roles: Role) -> Identity:
        """Identidad actual o falla con ``AuthError`` si su rol no esta incluido."""
        identity = self.current_identity()
        if identity.role not in roles:
            wanted = ", ".join(role.value for role in roles) or "ninguno"
            msg = f"Sin permiso: se requiere rol {wanted} (actual: {identity.role.value})."
            raise AuthError(msg)
        return identity

    def refresh(self) -> Identity:
        """Relee la sesion del disco y devuelve la identidad vigente."""
        return self.current_identity()

    def write_session(self, face: EnrolledFace) -> None:
        """Persiste la sesion tras un login confirmado (edge-triggered)."""
        now = datetime.fromtimestamp(self._clock(), tz=UTC)
        authenticated_at = now.isoformat()
        expires_at = ""
        if self._timeout_seconds > 0:
            expires_at = (now + timedelta(seconds=self._timeout_seconds)).isoformat()
        _atomic_write_json(
            self._session_path(),
            {
                SESSION_FACE_ID_KEY: face.face_id,
                SESSION_AUTH_AT_KEY: authenticated_at,
                SESSION_EXPIRES_AT_KEY: expires_at,
            },
        )

    def clear_session(self) -> None:
        """Borra la sesion (logout); si no hay, no hace nada."""
        try:
            self._session_path().unlink(missing_ok=True)
        except OSError as exc:
            LOGGER.warning("No se pudo borrar la sesion (%s).", exc)


class AllowAllIdentityProvider(IdentityProvider):
    """Null Object para modo abierto: identidad local con acceso total.

    Con ``require_login: false`` (defecto) el launcher lo usa cuando no hay
    sesion, para no romper los flujos sin enrolar. ``authenticated_at`` queda
    vacio porque no hubo un login real.
    """

    def __init__(self, *, role: Role = Role.ADMIN) -> None:
        self._identity = Identity(
            face_id=LOCAL_IDENTITY_FACE_ID,
            name=LOCAL_IDENTITY_NAME,
            role=role,
            authenticated_at="",
        )

    def current_identity(self) -> Identity:
        """Identidad local sintetizada, siempre la misma."""
        return self._identity

    def require_role(self, *roles: Role) -> Identity:  # noqa: ARG002
        """Devuelve la identidad sin comprobar (modo abierto)."""
        return self._identity

    def refresh(self) -> Identity:
        """Devuelve la identidad sin releer nada."""
        return self._identity
