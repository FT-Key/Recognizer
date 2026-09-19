"""Puerto del registro de accesos (logins faciales).

La implementacion actual es `FileAccessLogRepository` (JSONL + imagenes en
disco). Una futura base de datos (SQLite/Postgres para auditoria distribuida)
solo tendria que implementar este mismo puerto, sin tocar el dominio ni los
runners.
"""

from pathlib import Path
from typing import Protocol

from recognizer.core.domain.access import AccessEvent


class AccessLogRepository(Protocol):
    """Registra y consulta los eventos de acceso confirmados."""

    def append(self, *, event: AccessEvent, image: bytes | None) -> AccessEvent:
        """Registra el evento; si ``image`` no es ``None`` guarda la foto.

        Devuelve el evento persistido, con ``image`` seteado al nombre de
        archivo de la foto (o ``""`` si no se capturo).
        """
        ...

    def list_all(self) -> tuple[AccessEvent, ...]:
        """Todos los eventos, ordenados por ``timestamp`` descendente."""
        ...

    def find_by_face(self, face_id: str) -> tuple[AccessEvent, ...]:
        """Eventos de ese rostro, ordenados por ``timestamp`` descendente."""
        ...

    def image_path(self, event: AccessEvent) -> Path | None:
        """Ruta de la foto del evento, o ``None`` si no tiene o no existe."""
        ...
