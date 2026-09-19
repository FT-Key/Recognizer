"""Tests del rol en el repositorio de rostros (migración y robustez), sin hardware."""

import json
from collections.abc import Callable
from pathlib import Path

from recognizer.adapters.file_face_repository import FileFaceRepository
from recognizer.core.domain.face import EnrolledFace, FaceEmbedding
from recognizer.core.domain.identity import Role

EMBEDDING: FaceEmbedding = (1.0, 0.0)
CREATED_AT = "2026-09-19T00:00:00+00:00"


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


def _mutate_face_json(
    store: Path, face_id: str, mutate: Callable[[dict[str, object]], object]
) -> None:
    path = store / f"{face_id}.json"
    payload: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_enrolled_face_defaults_to_operator() -> None:
    face = EnrolledFace(
        face_id="F-0001",
        name="Ada",
        embedding=EMBEDDING,
        samples=5,
        created_at=CREATED_AT,
    )

    assert face.role is Role.OPERATOR


def test_save_and_read_keeps_admin_role(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    repo = FileFaceRepository(store)
    repo.save(_face(role=Role.ADMIN))

    assert repo.find_by_id("F-0001") == _face(role=Role.ADMIN)


def test_save_and_read_keeps_viewer_role(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    repo = FileFaceRepository(store)
    repo.save(_face(role=Role.VIEWER))

    found = repo.find_by_id("F-0001")

    assert found is not None
    assert found.role is Role.VIEWER


def test_face_without_role_migrates_to_operator(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    repo = FileFaceRepository(store)
    repo.save(_face(role=Role.ADMIN))
    _mutate_face_json(store, "F-0001", lambda payload: payload.pop("role", None))

    found = FileFaceRepository(store).find_by_id("F-0001")

    assert found is not None
    assert found.role is Role.OPERATOR


def test_face_with_unknown_role_falls_back_to_viewer(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    repo = FileFaceRepository(store)
    repo.save(_face())
    _mutate_face_json(store, "F-0001", lambda payload: payload.update(role="superadmin"))

    found = FileFaceRepository(store).find_by_id("F-0001")

    assert found is not None
    assert found.role is Role.VIEWER


def test_face_with_non_string_role_falls_back_to_viewer(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    repo = FileFaceRepository(store)
    repo.save(_face())
    _mutate_face_json(store, "F-0001", lambda payload: payload.update(role=7))

    found = FileFaceRepository(store).find_by_id("F-0001")

    assert found is not None
    assert found.role is Role.VIEWER
