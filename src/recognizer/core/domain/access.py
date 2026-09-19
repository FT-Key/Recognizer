"""Eventos de acceso (login facial) para auditoria.

Un evento registra quien entro, con que rol, cuando y, si se pudo, la foto del
login. Es dominio puro: sin sistema de archivos ni OpenCV; el adaptador
`FileAccessLogRepository` materializa el evento en disco y adjunta el nombre de
la imagen.
"""

from dataclasses import dataclass

from recognizer.core.domain.identity import Role


@dataclass(frozen=True, slots=True)
class AccessEvent:
    """Un login confirmado: identidad, rol, instante (ISO UTC) y foto opcional.

    ``timestamp`` usa ISO 8601 en UTC (``datetime.now(UTC).isoformat()`` en el
    adaptador), de modo que el orden lexicografico coincide con el cronologico.
    ``image`` es el nombre de archivo de la foto del login dentro del almacen
    (``""`` si no se capturo).
    """

    face_id: str
    name: str
    role: Role
    timestamp: str
    image: str = ""
