"""Tests del login con clave de respaldo (runner sin camara) con dobles.

Se sustituyen config, repositorio, proveedor de sesion y registro de accesos por
dobles, de modo que se ejercita la logica real de ``run_face_login_password``
sin hardware ni InsightFace.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

import pytest

from recognizer.cli.apps import face_auth
from recognizer.core.config import AppConfig, FaceAuthConfig
from recognizer.core.constants import FACE_LOGIN_PASSWORD_PROMPT, FACE_LOGIN_USER_PROMPT
from recognizer.core.domain.access import AccessEvent, AccessMethod
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.domain.credentials import hash_password
from recognizer.core.domain.face import EnrolledFace, FaceEmbedding
from recognizer.core.domain.identity import Role

REQUEST = AppRunRequest(config_path=Path("config.yaml"), show_window=False)
TEST_LOGGER = logging.getLogger("recognizer.face.password.login.test")
EMBEDDING: FaceEmbedding = (1.0, 0.0)
CLAVE = "clave1"


class FakeRepository:
    """Doble de FileFaceRepository con una galeria fija."""

    def __init__(self, faces: tuple[EnrolledFace, ...] = ()) -> None:
        self._faces = faces

    def list_all(self) -> tuple[EnrolledFace, ...]:
        return self._faces


class FakeSessionProvider:
    """Doble de FileIdentityProvider que captura las sesiones escritas."""

    def __init__(self) -> None:
        self.written: list[EnrolledFace] = []

    def write_session(self, face: EnrolledFace) -> None:
        self.written.append(face)


class FakeAccessLog:
    """Doble de FileAccessLogRepository que captura los eventos."""

    def __init__(self) -> None:
        self.events: list[tuple[AccessEvent, bytes | None]] = []

    def append(self, *, event: AccessEvent, image: bytes | None) -> AccessEvent:
        self.events.append((event, image))
        return event


def _face(
    *, name: str = "Ada", password: str | None = CLAVE, national_id: str = "12345678"
) -> EnrolledFace:
    password_hash = hash_password(password, iterations=1000) if password is not None else ""
    return EnrolledFace(
        face_id="F-0001",
        name=name,
        embedding=EMBEDDING,
        samples=5,
        created_at="2026-09-19T00:00:00+00:00",
        role=Role.OPERATOR,
        password_hash=password_hash,
        national_id=national_id,
    )


def _reader(user: str, password: str) -> Callable[[str], str]:
    answers = {FACE_LOGIN_USER_PROMPT: user, FACE_LOGIN_PASSWORD_PROMPT: password}
    return lambda prompt: answers.get(prompt, "")


def _install(
    monkeypatch: pytest.MonkeyPatch,
    *,
    repository: FakeRepository,
    session: FakeSessionProvider,
    access: FakeAccessLog,
) -> None:
    config = AppConfig(face_auth=FaceAuthConfig(store_dir="faces", access_dir="access"))
    monkeypatch.setattr(face_auth, "prepare_workspace", lambda path: path)
    monkeypatch.setattr(face_auth, "load_config", lambda _path: config)
    monkeypatch.setattr(face_auth, "FileFaceRepository", lambda _path: repository)
    monkeypatch.setattr(face_auth, "_identity_provider", lambda *_args, **_kwargs: session)
    monkeypatch.setattr(face_auth, "FileAccessLogRepository", lambda _path: access)


def test_password_login_success_writes_session_and_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    face = _face()
    session = FakeSessionProvider()
    access = FakeAccessLog()
    _install(
        monkeypatch,
        repository=FakeRepository((face,)),
        session=session,
        access=access,
    )

    result = face_auth.run_face_login_password(REQUEST, reader=_reader("12.345.678", CLAVE))

    assert result == 0
    assert session.written == [face]
    assert len(access.events) == 1
    event, image = access.events[0]
    assert event.face_id == "F-0001"
    assert event.name == "Ada"
    assert event.method is AccessMethod.PASSWORD
    assert event.success is True
    assert image is None


def test_password_login_by_name_does_not_authenticate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    face = _face()
    session = FakeSessionProvider()
    access = FakeAccessLog()
    _install(
        monkeypatch,
        repository=FakeRepository((face,)),
        session=session,
        access=access,
    )

    result = face_auth.run_face_login_password(REQUEST, reader=_reader("Ada", CLAVE))

    assert result == 1
    assert session.written == []
    assert len(access.events) == 1
    event, _image = access.events[0]
    assert event.face_id == "Ada"
    assert event.success is False


def test_password_login_by_id_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    face = _face()
    session = FakeSessionProvider()
    _install(
        monkeypatch,
        repository=FakeRepository((face,)),
        session=session,
        access=FakeAccessLog(),
    )

    result = face_auth.run_face_login_password(REQUEST, reader=_reader("F-0001", CLAVE))

    assert result == 0
    assert session.written == [face]


def test_password_login_wrong_password_returns_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSessionProvider()
    access = FakeAccessLog()
    _install(
        monkeypatch,
        repository=FakeRepository((_face(),)),
        session=session,
        access=access,
    )

    result = face_auth.run_face_login_password(REQUEST, reader=_reader("F-0001", "mala"))

    assert result == 1
    assert session.written == []
    assert len(access.events) == 1
    event, image = access.events[0]
    assert event.face_id == "F-0001"
    assert event.name == "Ada"
    assert event.method is AccessMethod.PASSWORD
    assert event.success is False
    assert image is None


def test_password_login_unknown_user_logs_failure_with_entered_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSessionProvider()
    access = FakeAccessLog()
    _install(
        monkeypatch,
        repository=FakeRepository((_face(),)),
        session=session,
        access=access,
    )

    result = face_auth.run_face_login_password(REQUEST, reader=_reader("Nadie", "mala"))

    assert result == 1
    assert session.written == []
    assert len(access.events) == 1
    event, _image = access.events[0]
    assert event.face_id == "Nadie"
    assert event.name == "Nadie"
    assert event.role is Role.VIEWER
    assert event.method is AccessMethod.PASSWORD
    assert event.success is False


def test_password_login_without_faces_returns_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSessionProvider()
    calls: list[str] = []

    def reader(prompt: str) -> str:
        calls.append(prompt)
        return ""

    _install(
        monkeypatch,
        repository=FakeRepository(()),
        session=session,
        access=FakeAccessLog(),
    )

    result = face_auth.run_face_login_password(REQUEST, reader=reader)

    assert result == 1
    assert calls == []
    assert session.written == []


def test_password_login_empty_reader_returns_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSessionProvider()
    access = FakeAccessLog()
    _install(
        monkeypatch,
        repository=FakeRepository((_face(),)),
        session=session,
        access=access,
    )

    result = face_auth.run_face_login_password(REQUEST, reader=_reader("", ""))

    assert result == 1
    assert session.written == []
    assert access.events == []
