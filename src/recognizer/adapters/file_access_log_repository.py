"""Registro de accesos (logins faciales) en JSONL + imagenes en disco.

Cada evento se agrega como una linea JSON en ``logins.jsonl`` y, si hay foto,
se escribe ``images/<fecha>_<id>.png``. El directorio se crea con acceso solo
del usuario (0o700 en POSIX). La lectura es tolerante a lineas corruptas para
no perder el historial por una escritura a medias.
"""

import json
import logging
import re
from contextlib import suppress
from dataclasses import replace
from pathlib import Path
from typing import cast

from recognizer.core.constants import (
    ACCESS_IMAGES_DIRNAME,
    ACCESS_LOG_FILENAME,
    FACE_PREVIEW_SUFFIX,
)
from recognizer.core.domain.access import AccessEvent
from recognizer.core.domain.identity import Role
from recognizer.core.errors import AccessLogError
from recognizer.core.ports.access_log import AccessLogRepository

LOGGER = logging.getLogger("recognizer.access_log")

ACCESS_FACE_ID_KEY = "face_id"
ACCESS_NAME_KEY = "name"
ACCESS_ROLE_KEY = "role"
ACCESS_TIMESTAMP_KEY = "timestamp"
ACCESS_IMAGE_KEY = "image"

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def _safe_token(value: str) -> str:
    """Convierte un texto en un token seguro para nombre de archivo."""
    return _UNSAFE_FILENAME_CHARS.sub("_", value)


def _event_to_payload(event: AccessEvent) -> dict[str, object]:
    """Representacion JSON plana del evento."""
    return {
        ACCESS_FACE_ID_KEY: event.face_id,
        ACCESS_NAME_KEY: event.name,
        ACCESS_ROLE_KEY: event.role.value,
        ACCESS_TIMESTAMP_KEY: event.timestamp,
        ACCESS_IMAGE_KEY: event.image,
    }


def _parse_event(line: str) -> AccessEvent | None:
    """Evento de una linea JSON; ``None`` si la linea esta corrupta."""
    try:
        raw = cast(object, json.loads(line))
    except ValueError:
        return None
    if not isinstance(raw, dict):
        return None
    face_id = raw.get(ACCESS_FACE_ID_KEY)
    name = raw.get(ACCESS_NAME_KEY)
    timestamp = raw.get(ACCESS_TIMESTAMP_KEY)
    image = raw.get(ACCESS_IMAGE_KEY, "")
    if not isinstance(face_id, str) or not face_id:
        return None
    if not isinstance(name, str) or not isinstance(timestamp, str) or not timestamp:
        return None
    if not isinstance(image, str):
        image = ""
    role = Role.VIEWER
    role_raw = raw.get(ACCESS_ROLE_KEY)
    if isinstance(role_raw, str):
        try:
            role = Role(role_raw)
        except ValueError:
            LOGGER.warning("Rol desconocido %r en el registro; se usa viewer.", role_raw)
    return AccessEvent(face_id=face_id, name=name, role=role, timestamp=timestamp, image=image)


class FileAccessLogRepository(AccessLogRepository):
    """Registra accesos en ``<access_dir>/logins.jsonl`` + fotos en ``images/``."""

    def __init__(self, access_dir: Path | str) -> None:
        self._access_dir = Path(access_dir)
        self._images_dir = self._access_dir / ACCESS_IMAGES_DIRNAME
        try:
            self._images_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            msg = f"No se pudo crear el directorio de accesos {self._access_dir}."
            raise AccessLogError(msg) from exc
        for directory in (self._access_dir, self._images_dir):
            with suppress(OSError):
                directory.chmod(0o700)

    @property
    def access_dir(self) -> Path:
        """Directorio donde viven el JSONL y las imagenes de accesos."""
        return self._access_dir

    def _log_path(self) -> Path:
        return self._access_dir / ACCESS_LOG_FILENAME

    def _image_name(self, event: AccessEvent) -> str:
        timestamp = _safe_token(event.timestamp)
        face_id = _safe_token(event.face_id)
        return f"{timestamp}_{face_id}{FACE_PREVIEW_SUFFIX}"

    def _append_line(self, event: AccessEvent) -> None:
        path = self._log_path()
        try:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(_event_to_payload(event), ensure_ascii=False) + "\n")
        except OSError as exc:
            msg = f"No se pudo escribir el registro de accesos {path}."
            raise AccessLogError(msg) from exc

    def append(self, *, event: AccessEvent, image: bytes | None) -> AccessEvent:
        """Registra el evento; con ``image`` escribe la foto y setea ``image``."""
        stored = event
        if image is not None:
            name = self._image_name(event)
            path = self._images_dir / name
            try:
                path.write_bytes(image)
            except OSError as exc:
                msg = f"No se pudo escribir la foto del acceso {path}."
                raise AccessLogError(msg) from exc
            stored = replace(event, image=name)
        self._append_line(stored)
        return stored

    def list_all(self) -> tuple[AccessEvent, ...]:
        """Todos los eventos, ordenados por ``timestamp`` descendente."""
        path = self._log_path()
        if not path.is_file():
            return ()
        events: list[AccessEvent] = []
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    event = _parse_event(stripped)
                    if event is None:
                        LOGGER.warning("Linea corrupta en el registro de accesos; se ignora.")
                        continue
                    events.append(event)
        except OSError as exc:
            msg = f"No se pudo leer el registro de accesos {path}."
            raise AccessLogError(msg) from exc
        events.sort(key=lambda event: event.timestamp, reverse=True)
        return tuple(events)

    def find_by_face(self, face_id: str) -> tuple[AccessEvent, ...]:
        """Eventos de ese rostro, ordenados por ``timestamp`` descendente."""
        return tuple(event for event in self.list_all() if event.face_id == face_id)

    def image_path(self, event: AccessEvent) -> Path | None:
        """Ruta de la foto del evento dentro de ``images/``, o ``None``.

        Rechaza nombres con separadores (path traversal) usando solo el nombre
        base del campo ``image``.
        """
        if not event.image:
            return None
        name = Path(event.image).name
        if not name or name != event.image:
            LOGGER.warning("Nombre de foto de acceso sospechoso %r; se ignora.", event.image)
            return None
        path = self._images_dir / name
        return path if path.is_file() else None
