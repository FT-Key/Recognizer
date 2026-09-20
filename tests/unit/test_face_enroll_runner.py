"""Tests del runner de enrolamiento (re-enrolamiento) con dobles, sin camara.

Se sustituye la camara, el modelo y el bucle de runtime por dobles que invocan
el callback de inferencia una vez, de modo que se ejercita la logica real de
`run_face_enroll` sin hardware ni InsightFace.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

import numpy as np
import pytest

from recognizer.adapters.file_face_repository import FileFaceRepository
from recognizer.cli.apps import face_auth
from recognizer.core.config import AppConfig, FaceAuthConfig
from recognizer.core.constants import (
    FACE_ENROLL_NAME_PROMPT,
    FACE_ENROLL_NATIONAL_ID_PROMPT,
    FACE_ENROLL_PASSWORD_CONFIRM_PROMPT,
    FACE_ENROLL_PASSWORD_PROMPT,
)
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.domain.credentials import hash_password, verify_password
from recognizer.core.domain.face import EnrolledFace, FaceBox, FaceObservation
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.identity import Identity, Role

ORIGINAL_CREATED_AT = "2020-01-01T00:00:00+00:00"
FRAME_SHAPE = (8, 8, 3)
EXISTING_CLAVE = "vieja1"
REQUEST = AppRunRequest(config_path=Path("config.yaml"), max_frames=1, show_window=False)
TEST_LOGGER = logging.getLogger("recognizer.face.enroll.runner.test")


class _FakeContext:
    """Context manager no-op para camara/modelo."""

    def __enter__(self) -> _FakeContext:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        return None


class FakePipelineBuilder:
    """Doble de PipelineBuilder: pipeline vacio."""

    def build(self) -> object:
        return object()


class FakeIdentityProvider:
    """Doble de IdentityProvider que siempre devuelve un admin."""

    def current_identity(self) -> Identity:
        return Identity(
            face_id="F-0000", name="root", role=Role.ADMIN, authenticated_at="2020-01-01T00:00:00Z"
        )

    def require_role(self, *_roles: Role) -> Identity:
        return self.current_identity()

    def refresh(self) -> Identity:
        return self.current_identity()


class FakeWorker:
    """Doble de _RecognitionWorker que captura el callback `process`."""

    captured: ClassVar[dict[str, object]] = {}

    def __init__(self, *, process: object, **_kwargs: object) -> None:
        FakeWorker.captured["process"] = process

    def __enter__(self) -> FakeWorker:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        return None


def _observation() -> FaceObservation:
    return FaceObservation(
        embedding=(1.0, 0.0),
        box=FaceBox(x_min=0.35, y_min=0.35, x_max=0.65, y_max=0.65, confidence=0.9),
        sharpness=120.0,
    )


def _install_runner_fakes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    config: AppConfig,
) -> None:
    FakeWorker.captured.clear()

    def fake_loop(_source: object, **_kwargs: object) -> tuple[int, float]:
        process = FakeWorker.captured["process"]
        frame = Frame(data=np.zeros(FRAME_SHAPE, dtype=np.uint8), timestamp=0.0)
        process(frame, (_observation(),))  # type: ignore[operator]
        return 1, 1.0

    monkeypatch.setattr(face_auth, "prepare_workspace", lambda path: path)
    monkeypatch.setattr(face_auth, "load_config", lambda _path: config)
    monkeypatch.setattr(face_auth, "_identity_provider", lambda *_a, **_k: FakeIdentityProvider())
    monkeypatch.setattr(
        face_auth, "resolve_camera_config", lambda *, app_config, **_kwargs: app_config.camera
    )
    monkeypatch.setattr(face_auth, "OpenCVCamera", lambda *_a, **_k: object())
    monkeypatch.setattr(face_auth, "LatestFrameSource", lambda *_a, **_k: _FakeContext())
    monkeypatch.setattr(face_auth, "InsightFaceRecognizer", lambda *_a, **_k: _FakeContext())
    monkeypatch.setattr(face_auth, "PipelineBuilder", FakePipelineBuilder)
    monkeypatch.setattr(face_auth, "_RecognitionWorker", FakeWorker)
    monkeypatch.setattr(face_auth, "run_camera_loop", fake_loop)


def _existing_face(
    face_id: str, *, password_hash: str = "", national_id: str = "12345678"
) -> EnrolledFace:
    return EnrolledFace(
        face_id=face_id,
        name="Ada",
        embedding=(0.0, 1.0),
        samples=5,
        created_at=ORIGINAL_CREATED_AT,
        role=Role.ADMIN,
        preview="",
        password_hash=password_hash,
        national_id=national_id,
    )


def _enroll_answers(
    *,
    name: str = "Nuevo",
    national_id: str = "23456789",
    clave: str = "clave1",
    confirmacion: str = "clave1",
) -> dict[str, str]:
    """Respuestas del lector para un alta (el primer rostro no pide rol)."""
    return {
        FACE_ENROLL_NAME_PROMPT: name,
        FACE_ENROLL_NATIONAL_ID_PROMPT: national_id,
        FACE_ENROLL_PASSWORD_PROMPT: clave,
        FACE_ENROLL_PASSWORD_CONFIRM_PROMPT: confirmacion,
    }


def _reader(answers: dict[str, str]) -> Callable[[str], str]:
    """Lector en cola que responde por prompt (claves de ``core.constants``)."""
    return lambda prompt: answers.get(prompt, "")


def test_reenroll_keeps_name_role_and_created_at(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tmp_path / "faces"
    repo = FileFaceRepository(store)
    existing_hash = hash_password(EXISTING_CLAVE, iterations=1000)
    repo.save(_existing_face("F-0007", password_hash=existing_hash))
    config = AppConfig(face_auth=FaceAuthConfig(store_dir=str(store), enrollment_samples=1))
    _install_runner_fakes(monkeypatch, config=config)

    result = face_auth.run_face_enroll(REQUEST, face_id="F-0007", reader=lambda _prompt: "")

    assert result == 0
    found = repo.find_by_id("F-0007")
    assert found is not None
    assert found.name == "Ada"
    assert found.role is Role.ADMIN
    assert found.created_at == ORIGINAL_CREATED_AT
    assert found.samples == 1
    assert found.preview == "F-0007.png"
    assert found.password_hash == existing_hash
    assert verify_password(EXISTING_CLAVE, found.password_hash)
    assert found.national_id == "12345678"
    assert repo.preview_path("F-0007") is not None


def test_reenroll_with_new_national_id_updates_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tmp_path / "faces"
    repo = FileFaceRepository(store)
    repo.save(_existing_face("F-0007"))
    config = AppConfig(face_auth=FaceAuthConfig(store_dir=str(store), enrollment_samples=1))
    _install_runner_fakes(monkeypatch, config=config)
    reader = _reader({FACE_ENROLL_NATIONAL_ID_PROMPT: "87.654.321"})

    result = face_auth.run_face_enroll(REQUEST, face_id="F-0007", reader=reader)

    assert result == 0
    found = repo.find_by_id("F-0007")
    assert found is not None
    assert found.national_id == "87654321"


def test_reenroll_missing_face_returns_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = tmp_path / "faces"
    config = AppConfig(face_auth=FaceAuthConfig(store_dir=str(store), enrollment_samples=1))
    _install_runner_fakes(monkeypatch, config=config)

    result = face_auth.run_face_enroll(REQUEST, face_id="F-9999")

    assert result == 1
    assert FileFaceRepository(store).list_all() == ()


def test_enroll_with_password_persists_verifiable_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tmp_path / "faces"
    config = AppConfig(face_auth=FaceAuthConfig(store_dir=str(store), enrollment_samples=1))
    _install_runner_fakes(monkeypatch, config=config)
    reader = _reader(_enroll_answers())

    result = face_auth.run_face_enroll(REQUEST, reader=reader)

    assert result == 0
    faces = FileFaceRepository(store).list_all()
    assert len(faces) == 1
    found = faces[0]
    assert re.match(r"^F-[A-Z0-9]{4}$", found.face_id) is not None
    assert found.name == "Nuevo"
    assert found.national_id == "23456789"
    assert found.password_hash
    assert verify_password("clave1", found.password_hash)
    assert not verify_password("otra", found.password_hash)


def test_enroll_invalid_national_id_returns_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tmp_path / "faces"
    config = AppConfig(face_auth=FaceAuthConfig(store_dir=str(store), enrollment_samples=1))
    _install_runner_fakes(monkeypatch, config=config)
    reader = _reader(_enroll_answers(national_id="ABC"))

    result = face_auth.run_face_enroll(REQUEST, reader=reader)

    assert result == 1
    assert FileFaceRepository(store).list_all() == ()


def test_enroll_duplicate_national_id_returns_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tmp_path / "faces"
    repo = FileFaceRepository(store)
    repo.save(_existing_face("F-0001", national_id="23456789"))
    config = AppConfig(face_auth=FaceAuthConfig(store_dir=str(store), enrollment_samples=1))
    _install_runner_fakes(monkeypatch, config=config)
    # La galeria ya no esta vacia: el operador del doble es admin.
    reader = _reader(_enroll_answers(national_id="23456789"))

    result = face_auth.run_face_enroll(REQUEST, reader=reader)

    assert result == 1
    assert len(FileFaceRepository(store).list_all()) == 1


def test_enroll_short_password_returns_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = tmp_path / "faces"
    config = AppConfig(face_auth=FaceAuthConfig(store_dir=str(store), enrollment_samples=1))
    _install_runner_fakes(monkeypatch, config=config)
    reader = _reader(_enroll_answers(clave="ab", confirmacion="ab"))

    result = face_auth.run_face_enroll(REQUEST, reader=reader)

    assert result == 1
    assert FileFaceRepository(store).list_all() == ()


def test_enroll_password_mismatch_returns_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tmp_path / "faces"
    config = AppConfig(face_auth=FaceAuthConfig(store_dir=str(store), enrollment_samples=1))
    _install_runner_fakes(monkeypatch, config=config)
    reader = _reader(_enroll_answers(clave="clave1", confirmacion="clave2"))

    result = face_auth.run_face_enroll(REQUEST, reader=reader)

    assert result == 1
    assert FileFaceRepository(store).list_all() == ()


def test_enroll_without_password_returns_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tmp_path / "faces"
    config = AppConfig(face_auth=FaceAuthConfig(store_dir=str(store), enrollment_samples=1))
    _install_runner_fakes(monkeypatch, config=config)
    reader = _reader(_enroll_answers(clave="", confirmacion=""))

    result = face_auth.run_face_enroll(REQUEST, reader=reader)

    assert result == 1
    assert FileFaceRepository(store).list_all() == ()


def test_enroll_without_national_id_returns_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tmp_path / "faces"
    config = AppConfig(face_auth=FaceAuthConfig(store_dir=str(store), enrollment_samples=1))
    _install_runner_fakes(monkeypatch, config=config)
    reader = _reader(_enroll_answers(national_id=""))

    result = face_auth.run_face_enroll(REQUEST, reader=reader)

    assert result == 1
    assert FileFaceRepository(store).list_all() == ()
