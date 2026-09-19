"""Tests del FileIdentityProvider (sesión en disco), sin hardware ni cámara."""

import json
import os
from pathlib import Path

import pytest

from recognizer.adapters.file_face_repository import FileFaceRepository
from recognizer.adapters.file_identity_provider import (
    SESSION_AUTH_AT_KEY,
    SESSION_EXPIRES_AT_KEY,
    SESSION_FACE_ID_KEY,
    AllowAllIdentityProvider,
    FileIdentityProvider,
)
from recognizer.core.constants import SESSION_FILENAME
from recognizer.core.domain.face import EnrolledFace, FaceEmbedding
from recognizer.core.domain.identity import Role, anonymous_identity
from recognizer.core.errors import AuthError, FaceRepositoryError

EMBEDDING: FaceEmbedding = (1.0, 0.0)
CREATED_AT = "2026-09-19T00:00:00+00:00"
BASE_TIME = 1_786_000_000.0
TIMEOUT_SECONDS = 3600


class _Clock:
    """Reloj mutable para controlar la expiración de la sesión en tests."""

    def __init__(self, now: float) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def _face(
    face_id: str = "F-0001",
    name: str = "Ada",
    role: Role = Role.OPERATOR,
) -> EnrolledFace:
    return EnrolledFace(
        face_id=face_id,
        name=name,
        embedding=EMBEDDING,
        samples=5,
        created_at=CREATED_AT,
        role=role,
    )


def _setup(
    store: Path,
    *,
    timeout_seconds: int = TIMEOUT_SECONDS,
    now: float = BASE_TIME,
) -> tuple[FileFaceRepository, FileIdentityProvider, _Clock]:
    repo = FileFaceRepository(store)
    clock = _Clock(now)
    provider = FileIdentityProvider(
        store,
        repo,
        session_timeout_seconds=timeout_seconds,
        clock=clock,
    )
    return repo, provider, clock


def test_without_session_returns_anonymous_viewer(tmp_path: Path) -> None:
    _, provider, _ = _setup(tmp_path / "faces")

    assert provider.current_identity() == anonymous_identity()


def test_corrupt_session_returns_anonymous_viewer(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    _, provider, _ = _setup(store)
    (store / SESSION_FILENAME).write_text("esto-no-es-json{{{", encoding="utf-8")

    assert provider.current_identity() == anonymous_identity()


def test_session_with_unknown_face_returns_anonymous(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    _, provider, _ = _setup(store)
    (store / SESSION_FILENAME).write_text(
        json.dumps(
            {
                SESSION_FACE_ID_KEY: "F-9999",
                SESSION_AUTH_AT_KEY: "2026-09-19T12:00:00+00:00",
                SESSION_EXPIRES_AT_KEY: "",
            }
        ),
        encoding="utf-8",
    )

    assert provider.current_identity() == anonymous_identity()


def test_write_session_makes_current_identity(tmp_path: Path) -> None:
    repo, provider, _ = _setup(tmp_path / "faces")
    face = _face(role=Role.ADMIN)
    repo.save(face)
    provider.write_session(face)

    identity = provider.current_identity()

    assert identity.face_id == "F-0001"
    assert identity.name == "Ada"
    assert identity.role is Role.ADMIN
    assert identity.authenticated_at != ""


def test_expired_session_returns_anonymous(tmp_path: Path) -> None:
    repo, provider, clock = _setup(tmp_path / "faces")
    face = _face()
    repo.save(face)
    provider.write_session(face)

    clock.now = BASE_TIME + TIMEOUT_SECONDS + 1.0

    assert provider.current_identity() == anonymous_identity()


def test_valid_session_survives_before_expiry(tmp_path: Path) -> None:
    repo, provider, clock = _setup(tmp_path / "faces")
    face = _face()
    repo.save(face)
    provider.write_session(face)

    clock.now = BASE_TIME + TIMEOUT_SECONDS - 1.0

    assert provider.current_identity().face_id == "F-0001"


def test_zero_timeout_session_never_expires(tmp_path: Path) -> None:
    repo, provider, clock = _setup(tmp_path / "faces", timeout_seconds=0)
    face = _face()
    repo.save(face)
    provider.write_session(face)

    clock.now = BASE_TIME + 10 * 365 * 24 * 3600.0

    assert provider.current_identity().face_id == "F-0001"


def test_clear_session_returns_to_anonymous(tmp_path: Path) -> None:
    repo, provider, _ = _setup(tmp_path / "faces")
    face = _face()
    repo.save(face)
    provider.write_session(face)
    provider.clear_session()

    assert provider.current_identity() == anonymous_identity()


def test_clear_session_without_session_does_nothing(tmp_path: Path) -> None:
    _, provider, _ = _setup(tmp_path / "faces")

    provider.clear_session()

    assert provider.current_identity() == anonymous_identity()


def test_require_role_returns_identity_when_allowed(tmp_path: Path) -> None:
    repo, provider, _ = _setup(tmp_path / "faces")
    repo.save(_face(role=Role.ADMIN))
    provider.write_session(_face(role=Role.ADMIN))

    assert provider.require_role(Role.ADMIN).role is Role.ADMIN


def test_require_role_raises_auth_error_when_denied(tmp_path: Path) -> None:
    repo, provider, _ = _setup(tmp_path / "faces")
    repo.save(_face(role=Role.VIEWER))
    provider.write_session(_face(role=Role.VIEWER))

    with pytest.raises(AuthError, match="Sin permiso"):
        provider.require_role(Role.ADMIN)


def test_require_role_without_session_raises_auth_error(tmp_path: Path) -> None:
    _, provider, _ = _setup(tmp_path / "faces")

    with pytest.raises(AuthError, match="Sin permiso"):
        provider.require_role(Role.OPERATOR)


def test_refresh_reloads_identity_from_disk(tmp_path: Path) -> None:
    repo, provider, _ = _setup(tmp_path / "faces")
    repo.save(_face(role=Role.OPERATOR))
    provider.write_session(_face(role=Role.OPERATOR))

    assert provider.refresh().role is Role.OPERATOR


def test_negative_timeout_is_rejected(tmp_path: Path) -> None:
    repo = FileFaceRepository(tmp_path / "faces")

    with pytest.raises(FaceRepositoryError, match="session_timeout_seconds"):
        FileIdentityProvider(tmp_path / "faces", repo, session_timeout_seconds=-1)


def test_store_dir_property_points_at_face_store(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    _, provider, _ = _setup(store)

    assert provider.store_dir == store


def test_non_dict_session_returns_anonymous(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    _, provider, _ = _setup(store)
    (store / SESSION_FILENAME).write_text("[1, 2, 3]", encoding="utf-8")

    assert provider.current_identity() == anonymous_identity()


def test_session_without_face_id_returns_anonymous(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    _, provider, _ = _setup(store)
    (store / SESSION_FILENAME).write_text(
        json.dumps({SESSION_AUTH_AT_KEY: "2026-09-19T12:00:00+00:00"}),
        encoding="utf-8",
    )

    assert provider.current_identity() == anonymous_identity()


def test_session_with_non_string_expiry_returns_anonymous(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    _, provider, _ = _setup(store)
    (store / SESSION_FILENAME).write_text(
        json.dumps(
            {
                SESSION_FACE_ID_KEY: "F-0001",
                SESSION_AUTH_AT_KEY: "2026-09-19T12:00:00+00:00",
                SESSION_EXPIRES_AT_KEY: 12345,
            }
        ),
        encoding="utf-8",
    )

    assert provider.current_identity() == anonymous_identity()


def test_write_session_failure_raises_repository_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, provider, _ = _setup(tmp_path / "faces")
    face = _face()
    repo.save(face)

    def boom(*_args: object, **_kwargs: object) -> object:
        raise OSError("sin espacio")

    monkeypatch.setattr(os, "fdopen", boom)

    with pytest.raises(FaceRepositoryError, match="No se pudo escribir"):
        provider.write_session(face)


def test_allow_all_provider_never_denies() -> None:
    provider = AllowAllIdentityProvider()

    assert provider.current_identity().role is Role.ADMIN
    assert provider.require_role(Role.ADMIN).role is Role.ADMIN
    assert provider.require_role().role is Role.ADMIN
    assert provider.refresh() == provider.current_identity()
