"""Almacen de rostros enrolados en JSON (una app local, sin red).

Los embeddings son datos biometricos: el directorio se crea con acceso solo
del usuario (0o700 en POSIX) y el cambio a una futura ``DbFaceRepository``
(SQLite/Postgres para login distribuido) solo implementa el puerto
``FaceRepository`` sin tocar el dominio.
"""

import json
import logging
import os
import re
import tempfile
from contextlib import suppress
from dataclasses import replace
from pathlib import Path
from typing import cast

from recognizer.core.constants import FACE_PREVIEW_SUFFIX
from recognizer.core.domain.face import EnrolledFace, next_face_id
from recognizer.core.domain.identity import Role
from recognizer.core.errors import FaceRepositoryError
from recognizer.core.ports.face_repository import FaceRepository

LOGGER = logging.getLogger("recognizer.face_store")

FACE_ID_PATTERN = r"^F-\d{4}$"
INDEX_FILENAME = "index.json"
FACE_SUFFIX = ".json"
FACE_FILE_TEMPLATE = "{face_id}.json"
INDEX_COUNTER_KEY = "counter"
INDEX_FACES_KEY = "faces"
FACE_ID_KEY = "face_id"
FACE_NAME_KEY = "name"
FACE_EMBEDDING_KEY = "embedding"
FACE_SAMPLES_KEY = "samples"
FACE_CREATED_AT_KEY = "created_at"
FACE_ROLE_KEY = "role"
FACE_PREVIEW_KEY = "preview"
FACE_PASSWORD_KEY = "password_hash"
FACE_NATIONAL_ID_KEY = "national_id"


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


class FileFaceRepository(FaceRepository):
    """Guarda rostros en ``<store_dir>/index.json`` + ``<id>.json`` por cara."""

    def __init__(self, store_dir: Path | str) -> None:
        self._store_dir = Path(store_dir)
        self._store_dir.mkdir(parents=True, exist_ok=True)
        with suppress(OSError):
            self._store_dir.chmod(0o700)

    @staticmethod
    def _require_face_id(face_id: str) -> None:
        """Rechaza ids fuera del formato ``F-0001`` (evita path traversal)."""
        if re.match(FACE_ID_PATTERN, face_id) is None:
            msg = f"face_id invalido: {face_id!r} (se espera F-0001)."
            raise FaceRepositoryError(msg)

    @property
    def store_dir(self) -> Path:
        """Directorio donde viven el indice y las caras."""
        return self._store_dir

    def _index_path(self) -> Path:
        return self._store_dir / INDEX_FILENAME

    def _face_path(self, face_id: str) -> Path:
        self._require_face_id(face_id)
        return self._store_dir / FACE_FILE_TEMPLATE.format(face_id=face_id)

    def _preview_path(self, face_id: str) -> Path:
        self._require_face_id(face_id)
        return self._store_dir / f"{face_id}{FACE_PREVIEW_SUFFIX}"

    def _read_index(self) -> tuple[int, list[str]]:
        """Contador persistido y lista de ids conocidos (tolerante a corrupcion)."""
        path = self._index_path()
        if not path.is_file():
            return 0, []
        try:
            raw = cast(object, json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            LOGGER.warning("Indice facial ilegible (%s); se reconstruye.", exc)
            return 0, []
        if not isinstance(raw, dict):
            return 0, []
        counter_raw = raw.get(INDEX_COUNTER_KEY, 0)
        counter = counter_raw if isinstance(counter_raw, int) and counter_raw >= 0 else 0
        faces_raw = raw.get(INDEX_FACES_KEY, [])
        ids: list[str] = []
        if isinstance(faces_raw, list):
            for entry in faces_raw:
                if isinstance(entry, str) and entry:
                    ids.append(entry)
                elif isinstance(entry, dict):
                    face_id = entry.get(FACE_ID_KEY)
                    if isinstance(face_id, str) and face_id:
                        ids.append(face_id)
        return counter, ids

    def _write_index(self, *, counter: int, face_ids: list[str]) -> None:
        _atomic_write_json(
            self._index_path(),
            {INDEX_COUNTER_KEY: counter, INDEX_FACES_KEY: sorted(set(face_ids))},
        )

    def _read_face_file(self, face_id: str) -> EnrolledFace | None:
        path = self._face_path(face_id)
        if not path.is_file():
            return None
        try:
            raw = cast(object, json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            LOGGER.warning("Cara ilegible %s (%s); se ignora.", face_id, exc)
            return None
        if not isinstance(raw, dict):
            return None
        try:
            embedding_raw = raw[FACE_EMBEDDING_KEY]
            if not isinstance(embedding_raw, list):
                return None
            embedding = tuple(float(value) for value in embedding_raw)
            samples_raw = raw[FACE_SAMPLES_KEY]
            name_raw = raw[FACE_NAME_KEY]
            created_raw = raw[FACE_CREATED_AT_KEY]
            if not isinstance(samples_raw, int) or not isinstance(name_raw, str):
                return None
            if not isinstance(created_raw, str):
                return None
            if FACE_ROLE_KEY not in raw:
                # Migración 15a: las caras enroladas antes de los roles tenían
                # acceso total, se conservan como operator (documentado).
                LOGGER.info("Cara %s sin rol (legado 15a); se migra a operator.", face_id)
                role = Role.OPERATOR
            else:
                role_raw = raw.get(FACE_ROLE_KEY)
                role = Role.VIEWER
                if isinstance(role_raw, str):
                    try:
                        role = Role(role_raw)
                    except ValueError:
                        LOGGER.warning(
                            "Rol desconocido %r en %s; se usa viewer.", role_raw, face_id
                        )
                else:
                    LOGGER.warning("Rol invalido en %s; se usa viewer.", face_id)
            preview_raw = raw.get(FACE_PREVIEW_KEY, "")
            preview = preview_raw if isinstance(preview_raw, str) else ""
            password_raw = raw.get(FACE_PASSWORD_KEY, "")
            password_hash = password_raw if isinstance(password_raw, str) else ""
            national_id_raw = raw.get(FACE_NATIONAL_ID_KEY, "")
            national_id = national_id_raw if isinstance(national_id_raw, str) else ""
            return EnrolledFace(
                # El id del nombre de archivo manda: evita ids embebidos que no
                # coincidan (y que `list_all` devuelva ids no validados).
                face_id=face_id,
                name=name_raw,
                embedding=embedding,
                samples=samples_raw,
                created_at=created_raw,
                role=role,
                preview=preview,
                password_hash=password_hash,
                national_id=national_id,
            )
        except (KeyError, TypeError, ValueError):
            LOGGER.warning("Cara corrupta %s; se ignora.", face_id)
            return None

    def _known_ids(self) -> list[str]:
        """Ids del indice mas los archivos sueltos en disco.

        Solo se aceptan nombres con formato de id facial (``F-0001``), de modo
        que ``index.json``, ``session.json`` u otros JSON del directorio no se
        confundan con rostros.
        """
        _, indexed = self._read_index()
        on_disk = [
            path.stem
            for path in self._store_dir.glob(f"*{FACE_SUFFIX}")
            if re.match(FACE_ID_PATTERN, path.stem) is not None
        ]
        return sorted(
            name for name in set(indexed) | set(on_disk) if re.match(FACE_ID_PATTERN, name)
        )

    def next_id(self) -> str:
        """Siguiente id secuencial persistente (maximo en disco + 1)."""
        return next_face_id(self._known_ids())

    def save(self, face: EnrolledFace) -> None:
        """Guarda la cara y actualiza el indice con el contador maximo."""
        _atomic_write_json(
            self._face_path(face.face_id),
            {
                FACE_ID_KEY: face.face_id,
                FACE_NAME_KEY: face.name,
                FACE_EMBEDDING_KEY: list(face.embedding),
                FACE_SAMPLES_KEY: face.samples,
                FACE_CREATED_AT_KEY: face.created_at,
                FACE_ROLE_KEY: face.role.value,
                FACE_PREVIEW_KEY: face.preview,
                FACE_PASSWORD_KEY: face.password_hash,
                FACE_NATIONAL_ID_KEY: face.national_id,
            },
        )
        counter, _ = self._read_index()
        known = self._known_ids()
        highest = 0
        for face_id in known:
            suffix = face_id[2:] if face_id.startswith("F-") else ""
            if suffix.isdigit():
                highest = max(highest, int(suffix))
        self._write_index(counter=max(counter, highest), face_ids=known)

    def update(self, face: EnrolledFace) -> None:
        """Actualiza un rostro existente; delega en ``save``."""
        self.save(face)

    def delete(self, face_id: str) -> None:
        """Borra el rostro y su foto, y lo quita del indice (contador intacto)."""
        self._require_face_id(face_id)
        try:
            self._face_path(face_id).unlink(missing_ok=True)
            self._preview_path(face_id).unlink(missing_ok=True)
        except OSError as exc:
            msg = f"No se pudo borrar el rostro {face_id}."
            raise FaceRepositoryError(msg) from exc
        counter, _ = self._read_index()
        remaining = [known for known in self._known_ids() if known != face_id]
        self._write_index(counter=counter, face_ids=remaining)

    def list_all(self) -> tuple[EnrolledFace, ...]:
        """Todas las caras legibles, ordenadas por id."""
        faces: list[EnrolledFace] = []
        for face_id in self._known_ids():
            face = self._read_face_file(face_id)
            if face is not None:
                faces.append(face)
        faces.sort(key=lambda face: face.face_id)
        return tuple(faces)

    def find_by_id(self, face_id: str) -> EnrolledFace | None:
        """Cara con ese id o ``None`` si no existe."""
        self._require_face_id(face_id)
        return self._read_face_file(face_id)

    def find_by_name(self, name: str) -> tuple[EnrolledFace, ...]:
        """Caras con ese nombre exacto, ordenadas por id."""
        return tuple(face for face in self.list_all() if face.name == name)

    def save_preview(self, *, face_id: str, image: bytes) -> str:
        """Guarda la foto de enrolamiento ``<id>.png`` y la asocia al JSON.

        Si el rostro aun no tiene JSON (enrolamiento en curso) solo escribe la
        imagen; el runner guarda luego el ``EnrolledFace`` con ``preview``.
        Devuelve el nombre de archivo.
        """
        path = self._preview_path(face_id)
        try:
            path.write_bytes(image)
        except OSError as exc:
            msg = f"No se pudo escribir la foto {path}."
            raise FaceRepositoryError(msg) from exc
        face = self._read_face_file(face_id)
        if face is not None and face.preview != path.name:
            self.save(replace(face, preview=path.name))
        return path.name

    def preview_path(self, face_id: str) -> Path | None:
        """Ruta de la foto de enrolamiento o ``None`` si no existe."""
        path = self._preview_path(face_id)
        return path if path.is_file() else None
