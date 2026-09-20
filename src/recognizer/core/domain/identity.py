"""Identidad y permisos por rol (dominio puro).

Los roles forman una jerarquia (admin > operator > viewer). La matriz por
defecto vive en ``DEFAULT_PERMISSIONS`` indexada por app, para que el
override de config ``face_auth.permissions`` (``{app_id: [roles]}``) se
fusione por clave. Sin sesion se usa la identidad invitada
(:func:`anonymous_identity`, rol viewer); el modo abierto
(``require_login: false``) usa :class:`AllowAllPolicy` en el launcher.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from recognizer.core.constants import ANONYMOUS_FACE_ID, ANONYMOUS_NAME
from recognizer.core.domain.app import AppCatalog, AppId, AppInfo
from recognizer.core.errors import ConfigError


class Role(StrEnum):
    """Rol de un rostro enrolado; el orden jerarquico es admin > operator > viewer."""

    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


@dataclass(frozen=True, slots=True)
class Identity:
    """Quien opera: rostro enrolado con rol y momento del login (ISO)."""

    face_id: str
    name: str
    role: Role
    authenticated_at: str


ANONYMOUS: Identity = Identity(
    face_id=ANONYMOUS_FACE_ID, name=ANONYMOUS_NAME, role=Role.VIEWER, authenticated_at=""
)


def anonymous_identity() -> Identity:
    """Identidad invitada (sin login): rol viewer y sin marca temporal.

    Se usa ``face_id="anonimo"`` (no "") para distinguirla en logs y evitar
    colisiones con comprobaciones de "sin id". Al ser frozen, se comparte la
    instancia sin riesgo.
    """
    return ANONYMOUS


@dataclass(frozen=True, slots=True)
class SessionRecord:
    """Sesion persistida: quien se autentico y hasta cuando vale."""

    face_id: str
    authenticated_at: str
    expires_at: str  # "" = sin expiracion (session_timeout_seconds: 0)


def session_expired(record: SessionRecord, *, now_iso: str) -> bool:
    """Indica si la sesion caduco; falla cerrado ante expiracion corrupta.

    Una ``expires_at`` que no se puede comparar (o ya pasada) da la sesion
    por caducada y el launcher vuelve a la identidad invitada.
    """
    if not record.expires_at:
        return False
    try:
        expires = datetime.fromisoformat(record.expires_at)
        now = datetime.fromisoformat(now_iso)
    except ValueError:
        return True
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return now >= expires


DEFAULT_PERMISSIONS: dict[AppId, tuple[Role, ...]] = {
    AppId.GESTURES: (Role.ADMIN, Role.OPERATOR, Role.VIEWER),
    AppId.POSTURE: (Role.ADMIN, Role.OPERATOR, Role.VIEWER),
    AppId.PEOPLE_COUNTER: (Role.ADMIN, Role.OPERATOR),
    AppId.ANTI_INTRUDER: (Role.ADMIN, Role.OPERATOR),
    AppId.FACE_AUTH: (Role.ADMIN, Role.OPERATOR),
    AppId.ASSISTANCE: (Role.ADMIN, Role.OPERATOR),
    AppId.LOITERING: (Role.ADMIN, Role.OPERATOR),
    AppId.VACANCY: (Role.ADMIN, Role.OPERATOR),
    AppId.VEHICLE_COUNTER: (Role.ADMIN, Role.OPERATOR),
    AppId.PRIVACY_BLUR: (Role.ADMIN, Role.OPERATOR),
    AppId.FALL_DETECTOR: (Role.ADMIN, Role.OPERATOR),
    AppId.GENDER_AGE: (Role.ADMIN, Role.OPERATOR),
    AppId.DROWSINESS: (Role.ADMIN, Role.OPERATOR),
    AppId.OCR_READER: (Role.ADMIN, Role.OPERATOR),
    AppId.PPE_DETECTOR: (Role.ADMIN,),
    AppId.INVENTORY: (Role.ADMIN,),
}


def normalize_overrides(
    raw: Mapping[str, tuple[Role, ...] | list[Role]],
) -> dict[AppId, tuple[Role, ...]]:
    """Convierte overrides ``{app_id: [roles]}`` a claves ``AppId``.

    Raises:
        ConfigError: si alguna clave no es una aplicacion conocida.
    """
    normalized: dict[AppId, tuple[Role, ...]] = {}
    for key, roles in raw.items():
        try:
            app_id = AppId(key)
        except ValueError as exc:
            msg = f"Permiso para aplicacion desconocida: {key}"
            raise ConfigError(msg) from exc
        normalized[app_id] = tuple(roles)
    return normalized


class PolicyEngine:
    """Strategy de permisos: que apps puede lanzar cada rol y quien enrola."""

    def __init__(self, permissions: Mapping[AppId, tuple[Role, ...]] | None = None) -> None:
        self._permissions = dict(DEFAULT_PERMISSIONS) if permissions is None else dict(permissions)

    def can_launch(self, identity: Identity, *, app_id: AppId) -> bool:
        """Indica si el rol de la identidad puede abrir esa app."""
        return identity.role in self._permissions.get(app_id, ())

    def can_enroll(self, identity: Identity, *, target_role: Role) -> bool:
        """Indica si la identidad puede enrolar un rostro con ese rol.

        Admin enrola todo; operator enrola viewer/operator (nunca admin, por
        minimo privilegio y sin override de config); viewer e invitados nada.
        """
        match identity.role:
            case Role.ADMIN:
                return True
            case Role.OPERATOR:
                match target_role:
                    case Role.ADMIN:
                        return False
                    case _:
                        return True
            case _:
                return False

    def visible_apps(self, identity: Identity, *, catalog: AppCatalog) -> tuple[AppInfo, ...]:
        """Apps lanzables por la identidad, manteniendo el orden del catalogo."""
        return tuple(info for info in catalog.apps if self.can_launch(identity, app_id=info.app_id))


class AllowAllPolicy:
    """Null Object: todo permitido (modo sin login y dobles de tests)."""

    def can_launch(self, identity: Identity, *, app_id: AppId) -> bool:  # noqa: ARG002
        """Siempre ``True``."""
        return True

    def can_enroll(self, identity: Identity, *, target_role: Role) -> bool:  # noqa: ARG002
        """Siempre ``True``."""
        return True

    def visible_apps(
        self,
        identity: Identity,  # noqa: ARG002
        *,
        catalog: AppCatalog,
    ) -> tuple[AppInfo, ...]:
        """Todo el catalogo, en su orden."""
        return tuple(catalog.apps)


AppPolicy = PolicyEngine | AllowAllPolicy
"""Politica usable por el launcher: motor real o Null Object en modo abierto."""
