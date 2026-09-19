"""Tests del repositorio de rostros en disco (JSON), sin hardware."""

from pathlib import Path

from recognizer.adapters.file_face_repository import FileFaceRepository
from recognizer.core.domain.face import EnrolledFace, FaceEmbedding

EMBEDDING: FaceEmbedding = (1.0, 0.0)
OTHER_EMBEDDING: FaceEmbedding = (0.0, 1.0)
CREATED_AT = "2026-09-19T00:00:00+00:00"


def _face(face_id: str = "F-0001", name: str = "Ada") -> EnrolledFace:
    return EnrolledFace(
        face_id=face_id,
        name=name,
        embedding=EMBEDDING,
        samples=5,
        created_at=CREATED_AT,
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
