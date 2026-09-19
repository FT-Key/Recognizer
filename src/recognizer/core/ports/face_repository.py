"""Puerto del almacen de rostros enrolados.

La implementacion actual es `FileFaceRepository` (JSON en disco, una app
local). Una futura `DbFaceRepository` (SQLite/Postgres) solo tendria que
implementar este mismo puerto para llevar el login facial a un despliegue
distribuido, sin tocar el dominio ni los runners.
"""

from pathlib import Path
from typing import Protocol

from recognizer.core.domain.face import EnrolledFace


class FaceRepository(Protocol):
    """Guarda y recupera rostros enrolados por id o por nombre."""

    def next_id(self) -> str:
        """Siguiente identificador secuencial libre (``F-0001``, ...)."""
        ...

    def save(self, face: EnrolledFace) -> None:
        """Guarda o actualiza un rostro enrolado."""
        ...

    def update(self, face: EnrolledFace) -> None:
        """Actualiza un rostro existente (nombre, rol, embedding...)."""
        ...

    def delete(self, face_id: str) -> None:
        """Borra un rostro y su foto; el contador secuencial no retrocede."""
        ...

    def list_all(self) -> tuple[EnrolledFace, ...]:
        """Todos los rostros enrolados, ordenados por id."""
        ...

    def find_by_id(self, face_id: str) -> EnrolledFace | None:
        """Rostro con ese id o ``None`` si no existe."""
        ...

    def find_by_name(self, name: str) -> tuple[EnrolledFace, ...]:
        """Rostros con ese nombre exacto (puede haber homonimos)."""
        ...

    def save_preview(self, *, face_id: str, image: bytes) -> str:
        """Guarda la foto de enrolamiento (PNG) y devuelve su nombre de archivo."""
        ...

    def preview_path(self, face_id: str) -> Path | None:
        """Ruta de la foto de enrolamiento o ``None`` si no existe."""
        ...
