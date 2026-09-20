"""Tests del repositorio de rostros en disco (JSON), sin hardware."""

from pathlib import Path

import pytest

from recognizer.adapters.file_face_repository import FileFaceRepository
from recognizer.core.constants import FACE_PREVIEW_SUFFIX
from recognizer.core.domain.face import EnrolledFace, FaceEmbedding
from recognizer.core.domain.identity import Role
from recognizer.core.errors import FaceRepositoryError

EMBEDDING: FaceEmbedding = (1.0, 0.0)
OTHER_EMBEDDING: FaceEmbedding = (0.0, 1.0)
CREATED_AT = "2026-09-19T00:00:00+00:00"
PREVIEW_BYTES = b"\x89PNG\r\n\x1a\nfake"
PREVIEW_NAME = f"F-0001{FACE_PREVIEW_SUFFIX}"


def _face(
    face_id: str = "F-0001",
    name: str = "Ada",
    *,
    role: Role = Role.OPERATOR,
    preview: str = "",
    password_hash: str = "",
    national_id: str = "",
) -> EnrolledFace:
    return EnrolledFace(
        face_id=face_id,
        name=name,
        embedding=EMBEDDING,
        samples=5,
        created_at=CREATED_AT,
        role=role,
        preview=preview,
        password_hash=password_hash,
        national_id=national_id,
    )


def test_next_id_starts_at_one_on_empty_store(tmp_path: Path) -> None:
    repo = FileFaceRepository(tmp_path / "faces")
    assert repo.next_id() == "F-0001"


def test_save_and_find_by_id_roundtrip(tmp_path: Path) -> None:
    repo = FileFaceRepository(tmp_path / "faces")
    repo.save(_face())
    found = repo.find_by_id("F-0001")
    assert found == _face()


def test_find_by_id_missing_returns_none(tmp_path: Path) -> None:
    repo = FileFaceRepository(tmp_path / "faces")
    assert repo.find_by_id("F-9999") is None


def test_next_id_advances_after_save(tmp_path: Path) -> None:
    repo = FileFaceRepository(tmp_path / "faces")
    repo.save(_face("F-0001"))
    assert repo.next_id() == "F-0002"
    repo.save(_face("F-0002", "Bo"))
    assert repo.next_id() == "F-0003"


def test_counter_persists_across_instances(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    FileFaceRepository(store).save(_face("F-0001"))
    reopened = FileFaceRepository(store)
    assert reopened.next_id() == "F-0002"
    assert reopened.find_by_id("F-0001") == _face("F-0001")


def test_list_all_returns_sorted_faces(tmp_path: Path) -> None:
    repo = FileFaceRepository(tmp_path / "faces")
    repo.save(_face("F-0002", "Bo"))
    repo.save(_face("F-0001"))
    faces = repo.list_all()
    assert [face.face_id for face in faces] == ["F-0001", "F-0002"]


def test_list_all_empty_store_returns_empty(tmp_path: Path) -> None:
    repo = FileFaceRepository(tmp_path / "faces")
    assert repo.list_all() == ()


def test_find_by_name_matches_exact_name(tmp_path: Path) -> None:
    repo = FileFaceRepository(tmp_path / "faces")
    repo.save(_face("F-0001", "Ada"))
    repo.save(_face("F-0002", "Bo"))
    matches = repo.find_by_name("Ada")
    assert [face.face_id for face in matches] == ["F-0001"]


def test_find_by_name_without_matches_returns_empty(tmp_path: Path) -> None:
    repo = FileFaceRepository(tmp_path / "faces")
    repo.save(_face("F-0001", "Ada"))
    assert repo.find_by_name("Zoe") == ()


def test_save_updates_existing_face(tmp_path: Path) -> None:
    repo = FileFaceRepository(tmp_path / "faces")
    repo.save(_face("F-0001", "Ada"))
    updated = EnrolledFace(
        face_id="F-0001",
        name="Ada",
        embedding=OTHER_EMBEDDING,
        samples=6,
        created_at=CREATED_AT,
    )
    repo.save(updated)
    assert repo.find_by_id("F-0001") == updated
    assert repo.next_id() == "F-0002"


def test_session_json_is_not_treated_as_face(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    repo = FileFaceRepository(store)
    repo.save(_face("F-0001", "Ada"))
    (store / "session.json").write_text('{"face_id": "F-0001"}', encoding="utf-8")

    assert [face.face_id for face in repo.list_all()] == ["F-0001"]
    assert repo.next_id() == "F-0002"
    assert repo.find_by_name("session") == ()


def test_legacy_index_with_non_face_ids_is_ignored(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    repo = FileFaceRepository(store)
    repo.save(_face("F-0001", "Ada"))
    (store / "index.json").write_text(
        '{"counter": 1, "faces": ["F-0001", "session"]}', encoding="utf-8"
    )

    assert [face.face_id for face in repo.list_all()] == ["F-0001"]
    assert repo.next_id() == "F-0002"


def test_save_preview_without_json_writes_image_only(tmp_path: Path) -> None:
    repo = FileFaceRepository(tmp_path / "faces")

    name = repo.save_preview(face_id="F-0001", image=PREVIEW_BYTES)

    assert name == PREVIEW_NAME
    assert repo.preview_path("F-0001") == repo.store_dir / PREVIEW_NAME
    assert repo.find_by_id("F-0001") is None


def test_save_preview_attaches_to_existing_face(tmp_path: Path) -> None:
    repo = FileFaceRepository(tmp_path / "faces")
    repo.save(_face())

    name = repo.save_preview(face_id="F-0001", image=PREVIEW_BYTES)

    found = repo.find_by_id("F-0001")
    assert found is not None
    assert found.preview == name
    assert repo.preview_path("F-0001") == repo.store_dir / name


def test_save_preview_is_idempotent(tmp_path: Path) -> None:
    repo = FileFaceRepository(tmp_path / "faces")
    repo.save(_face())

    first = repo.save_preview(face_id="F-0001", image=PREVIEW_BYTES)
    second = repo.save_preview(face_id="F-0001", image=PREVIEW_BYTES)

    found = repo.find_by_id("F-0001")
    assert first == second
    assert found is not None
    assert found.preview == first


def test_preview_path_missing_returns_none(tmp_path: Path) -> None:
    repo = FileFaceRepository(tmp_path / "faces")

    assert repo.preview_path("F-0001") is None


def test_save_preview_invalid_face_id_raises(tmp_path: Path) -> None:
    repo = FileFaceRepository(tmp_path / "faces")

    with pytest.raises(FaceRepositoryError, match="face_id invalido"):
        repo.save_preview(face_id="../escape", image=PREVIEW_BYTES)


def test_preview_roundtrip_persists_field(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    FileFaceRepository(store).save(_face(preview=PREVIEW_NAME))

    found = FileFaceRepository(store).find_by_id("F-0001")

    assert found is not None
    assert found.preview == PREVIEW_NAME


def test_password_hash_roundtrip_persists_field(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    encoded = "pbkdf2_sha256$1000$c2FsdA==$aGFzaA=="
    FileFaceRepository(store).save(_face(password_hash=encoded))

    found = FileFaceRepository(store).find_by_id("F-0001")

    assert found is not None
    assert found.password_hash == encoded


def test_legacy_face_without_password_reads_empty(tmp_path: Path) -> None:
    import json

    store = tmp_path / "faces"
    repo = FileFaceRepository(store)
    (store / "F-0001.json").write_text(
        json.dumps(
            {
                "face_id": "F-0001",
                "name": "Ada",
                "embedding": [1.0, 0.0],
                "samples": 5,
                "created_at": CREATED_AT,
                "role": "operator",
            }
        ),
        encoding="utf-8",
    )

    found = repo.find_by_id("F-0001")

    assert found is not None
    assert found.password_hash == ""
    assert found.national_id == ""


def test_national_id_roundtrip_persists_field(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    FileFaceRepository(store).save(_face(national_id="12345678"))

    found = FileFaceRepository(store).find_by_id("F-0001")

    assert found is not None
    assert found.national_id == "12345678"


def test_update_changes_name_role_and_preview(tmp_path: Path) -> None:
    repo = FileFaceRepository(tmp_path / "faces")
    repo.save(_face())

    repo.update(_face(name="Ada Lovelace", role=Role.ADMIN, preview=PREVIEW_NAME))

    found = repo.find_by_id("F-0001")
    assert found is not None
    assert found.name == "Ada Lovelace"
    assert found.role is Role.ADMIN
    assert found.preview == PREVIEW_NAME
    assert repo.next_id() == "F-0002"


def test_delete_removes_json_and_preview(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    repo = FileFaceRepository(store)
    repo.save(_face())
    repo.save_preview(face_id="F-0001", image=PREVIEW_BYTES)

    repo.delete("F-0001")

    assert repo.find_by_id("F-0001") is None
    assert repo.preview_path("F-0001") is None
    assert repo.list_all() == ()
    assert not (store / "F-0001.json").exists()
    assert not (store / PREVIEW_NAME).exists()


def test_delete_removes_id_from_index(tmp_path: Path) -> None:
    import json

    store = tmp_path / "faces"
    repo = FileFaceRepository(store)
    repo.save(_face())

    repo.delete("F-0001")

    payload = json.loads((store / "index.json").read_text(encoding="utf-8"))
    assert "F-0001" not in payload["faces"]


def test_delete_missing_face_is_noop(tmp_path: Path) -> None:
    repo = FileFaceRepository(tmp_path / "faces")

    repo.delete("F-0001")

    assert repo.list_all() == ()


def test_delete_invalid_face_id_raises(tmp_path: Path) -> None:
    repo = FileFaceRepository(tmp_path / "faces")

    with pytest.raises(FaceRepositoryError, match="face_id invalido"):
        repo.delete("../escape")


def test_corrupt_index_is_rebuilt(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    repo = FileFaceRepository(store)
    (store / "index.json").write_text("no json", encoding="utf-8")

    assert repo.list_all() == ()
    assert repo.next_id() == "F-0001"


def test_index_with_dict_entries_is_accepted(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    repo = FileFaceRepository(store)
    (store / "index.json").write_text(
        '{"counter": 1, "faces": [{"face_id": "F-0001"}]}', encoding="utf-8"
    )

    assert repo.next_id() == "F-0002"
    assert repo.list_all() == ()


def test_corrupt_face_file_is_ignored(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    repo = FileFaceRepository(store)
    (store / "F-0001.json").write_text("no json", encoding="utf-8")

    assert repo.find_by_id("F-0001") is None


def test_non_dict_face_file_is_ignored(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    repo = FileFaceRepository(store)
    (store / "F-0001.json").write_text("[1, 2]", encoding="utf-8")

    assert repo.find_by_id("F-0001") is None


def test_face_with_invalid_embedding_is_ignored(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    repo = FileFaceRepository(store)
    (store / "F-0001.json").write_text(
        (
            '{"face_id": "F-0001", "name": "Ada", "embedding": ["x"], '
            f'"samples": 5, "created_at": "{CREATED_AT}", "role": "admin"}}'
        ),
        encoding="utf-8",
    )

    assert repo.find_by_id("F-0001") is None


def test_save_error_when_tempfile_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_args: object, **_kwargs: object) -> tuple[int, str]:
        raise OSError("sin temporal")

    monkeypatch.setattr("tempfile.mkstemp", _boom)
    repo = FileFaceRepository(tmp_path / "faces")

    with pytest.raises(FaceRepositoryError, match="No se pudo escribir"):
        repo.save(_face())


def test_save_error_when_write_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_args: object, **_kwargs: object) -> object:
        raise OSError("sin descriptor")

    monkeypatch.setattr("os.fdopen", _boom)
    repo = FileFaceRepository(tmp_path / "faces")

    with pytest.raises(FaceRepositoryError, match="No se pudo escribir"):
        repo.save(_face())


def test_delete_error_when_face_path_is_directory(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    repo = FileFaceRepository(store)
    (store / "F-0001.json").mkdir()

    with pytest.raises(FaceRepositoryError, match="borrar"):
        repo.delete("F-0001")


def test_save_preview_error_when_target_is_directory(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    repo = FileFaceRepository(store)
    (store / PREVIEW_NAME).mkdir()

    with pytest.raises(FaceRepositoryError, match="foto"):
        repo.save_preview(face_id="F-0001", image=PREVIEW_BYTES)
