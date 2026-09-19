"""Tests del registro de accesos en disco (JSONL + fotos), sin hardware."""

import json
from pathlib import Path

import pytest

from recognizer.adapters.file_access_log_repository import FileAccessLogRepository
from recognizer.core.constants import ACCESS_IMAGES_DIRNAME, ACCESS_LOG_FILENAME
from recognizer.core.domain.access import AccessEvent
from recognizer.core.domain.identity import Role
from recognizer.core.errors import AccessLogError

TS_OLD = "2026-09-19T10:00:00+00:00"
TS_NEW = "2026-09-19T12:00:00+00:00"
PNG_BYTES = b"\x89PNG\r\n\x1a\nfake"


def _event(
    *,
    face_id: str = "F-0001",
    name: str = "Ada",
    role: Role = Role.ADMIN,
    timestamp: str = TS_OLD,
    image: str = "",
) -> AccessEvent:
    return AccessEvent(face_id=face_id, name=name, role=role, timestamp=timestamp, image=image)


def test_append_without_image_keeps_empty_image(tmp_path: Path) -> None:
    repo = FileAccessLogRepository(tmp_path / "access")

    stored = repo.append(event=_event(), image=None)

    assert stored.image == ""
    assert repo.list_all() == (stored,)
    assert list((repo.access_dir / ACCESS_IMAGES_DIRNAME).iterdir()) == []


def test_append_with_image_writes_png_and_sets_name(tmp_path: Path) -> None:
    repo = FileAccessLogRepository(tmp_path / "access")

    stored = repo.append(event=_event(), image=PNG_BYTES)

    assert stored.image.endswith(".png")
    image_path = repo.access_dir / ACCESS_IMAGES_DIRNAME / stored.image
    assert image_path.is_file()
    assert image_path.read_bytes() == PNG_BYTES


def test_list_all_orders_descending_by_timestamp(tmp_path: Path) -> None:
    repo = FileAccessLogRepository(tmp_path / "access")
    repo.append(event=_event(timestamp=TS_OLD, name="Viejo"), image=None)
    repo.append(event=_event(timestamp=TS_NEW, name="Nuevo"), image=None)

    names = [event.name for event in repo.list_all()]

    assert names == ["Nuevo", "Viejo"]


def test_find_by_face_filters_and_orders(tmp_path: Path) -> None:
    repo = FileAccessLogRepository(tmp_path / "access")
    repo.append(event=_event(face_id="F-0001", timestamp=TS_OLD), image=None)
    repo.append(event=_event(face_id="F-0002", timestamp=TS_NEW), image=None)
    repo.append(event=_event(face_id="F-0001", timestamp=TS_NEW), image=None)

    matches = repo.find_by_face("F-0001")

    assert [event.face_id for event in matches] == ["F-0001", "F-0001"]
    assert [event.timestamp for event in matches] == [TS_NEW, TS_OLD]


def test_find_by_face_unknown_returns_empty(tmp_path: Path) -> None:
    repo = FileAccessLogRepository(tmp_path / "access")
    repo.append(event=_event(), image=None)

    assert repo.find_by_face("F-9999") == ()


def test_list_all_tolerates_corrupt_lines(tmp_path: Path) -> None:
    repo = FileAccessLogRepository(tmp_path / "access")
    repo.append(event=_event(), image=None)
    log = repo.access_dir / ACCESS_LOG_FILENAME
    with log.open("a", encoding="utf-8") as handle:
        handle.write("esto no es json\n")
        handle.write(json.dumps([1, 2, 3]) + "\n")
        handle.write(json.dumps({"name": "sin id"}) + "\n")
        handle.write("\n")

    events = repo.list_all()

    assert len(events) == 1
    assert events[0].face_id == "F-0001"


def test_unknown_role_falls_back_to_viewer(tmp_path: Path) -> None:
    repo = FileAccessLogRepository(tmp_path / "access")
    payload = {
        "face_id": "F-0001",
        "name": "Ada",
        "role": "root",
        "timestamp": TS_OLD,
        "image": "",
    }
    (repo.access_dir / ACCESS_LOG_FILENAME).write_text(json.dumps(payload) + "\n", encoding="utf-8")

    events = repo.list_all()

    assert events[0].role is Role.VIEWER


def test_non_string_name_line_is_ignored(tmp_path: Path) -> None:
    repo = FileAccessLogRepository(tmp_path / "access")
    (repo.access_dir / ACCESS_LOG_FILENAME).write_text(
        json.dumps({"face_id": "F-0001", "name": 7, "timestamp": TS_OLD}) + "\n",
        encoding="utf-8",
    )

    assert repo.list_all() == ()


def test_append_line_error_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = FileAccessLogRepository(tmp_path / "access")
    monkeypatch.setattr(repo, "_log_path", lambda: repo.access_dir)

    with pytest.raises(AccessLogError, match="escribir el registro"):
        repo.append(event=_event(), image=None)


def test_append_image_error_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = FileAccessLogRepository(tmp_path / "access")
    monkeypatch.setattr(repo, "_image_name", lambda _event: "")

    with pytest.raises(AccessLogError, match="escribir la foto"):
        repo.append(event=_event(), image=PNG_BYTES)


def test_non_string_image_field_is_cleared(tmp_path: Path) -> None:
    repo = FileAccessLogRepository(tmp_path / "access")
    payload = {
        "face_id": "F-0001",
        "name": "Ada",
        "role": "admin",
        "timestamp": TS_OLD,
        "image": 7,
    }
    (repo.access_dir / ACCESS_LOG_FILENAME).write_text(json.dumps(payload) + "\n", encoding="utf-8")

    assert repo.list_all()[0].image == ""


def test_missing_log_returns_empty(tmp_path: Path) -> None:
    repo = FileAccessLogRepository(tmp_path / "access")

    assert repo.list_all() == ()


def test_constructor_creates_images_dir(tmp_path: Path) -> None:
    repo = FileAccessLogRepository(tmp_path / "access")

    assert (repo.access_dir / ACCESS_IMAGES_DIRNAME).is_dir()
    assert repo.access_dir == tmp_path / "access"


def test_constructor_fails_when_access_dir_is_a_file(tmp_path: Path) -> None:
    blocking = tmp_path / "access"
    blocking.write_text("no soy un directorio", encoding="utf-8")

    with pytest.raises(AccessLogError, match="directorio de accesos"):
        FileAccessLogRepository(blocking)
