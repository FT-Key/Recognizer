"""Eventos de acceso (login facial o con clave) para auditoria.

Un evento registra quien entro (o lo intento), con que rol, cuando, por que
medio, con que resultado y, si se pudo, la foto del login. Es dominio puro:
sin sistema de archivos ni OpenCV; el adaptador `FileAccessLogRepository`
materializa el evento en disco y adjunta el nombre de la imagen.
"""

from dataclasses import dataclass
from enum import StrEnum

from recognizer.core.domain.identity import Role


class AccessMethod(StrEnum):
    """Medio del intento de acceso: reconocimiento facial o clave de respaldo."""

    FACE = "facial"
    PASSWORD = "clave"  # noqa: S105 (etiqueta del medio, no un secreto)


@dataclass(frozen=True, slots=True)
class AccessEvent:
    """Un intento de acceso: identidad, rol, instante (ISO UTC), medio y resultado.

    ``timestamp`` usa ISO 8601 en UTC (``datetime.now(UTC).isoformat()`` en el
    adaptador), de modo que el orden lexicografico coincide con el cronologico.
    ``method`` indica si fue facial o con clave; ``success`` si entro. Los
    eventos anteriores a la etapa 15d-accesos-clave se leen como facial
    exitoso. ``image`` es el nombre de archivo de la foto del login dentro del
    almacen (``""`` si no se capturo; los logins con clave nunca tienen foto).
    """

    face_id: str
    name: str
    role: Role
    timestamp: str
    image: str = ""
    method: AccessMethod = AccessMethod.FACE
    success: bool = True
