"""Tests del enrolamiento por rol (builder y resolución), sin cámara ni modelos."""

import pytest

from recognizer.cli.apps.face_auth import _resolve_enroll_role
from recognizer.core.config import FaceAuthConfig
from recognizer.core.domain.face import EnrollmentBuilder, FaceBox, FaceObservation
from recognizer.core.domain.identity import Identity, Role

AUTH_AT = "2026-09-19T12:00:00+00:00"


def _operator(role: Role) -> Identity:
    return Identity(face_id="F-0001", name="Ada", role=role, authenticated_at=AUTH_AT)


def _good_observation() -> FaceObservation:
    box = FaceBox(x_min=0.35, y_min=0.35, x_max=0.65, y_max=0.65, confidence=0.9)
    return FaceObservation(embedding=(1.0, 0.0), box=box, sharpness=100.0)


def _complete_builder() -> EnrollmentBuilder:
    builder = EnrollmentBuilder(samples_required=2)
    assert builder.add(_good_observation()) is None
    assert builder.add(_good_observation()) is None
    return builder


def test_builder_build_keeps_admin_role() -> None:
    face = _complete_builder().build("F-0002", "Bo", role=Role.ADMIN)

    assert face.role is Role.ADMIN
    assert face.face_id == "F-0002"


def test_builder_build_defaults_to_operator() -> None:
    face = _complete_builder().build("F-0002", "Bo")

    assert face.role is Role.OPERATOR


def test_builder_build_without_samples_raises() -> None:
    builder = EnrollmentBuilder(samples_required=2)

    with pytest.raises(ValueError, match="Faltan muestras"):
        builder.build("F-0002", "Bo", role=Role.VIEWER)


def test_first_enrolled_face_is_admin() -> None:
    role = _resolve_enroll_role(
        operator=_operator(Role.VIEWER),
        is_first=True,
        face_config=FaceAuthConfig(),
    )

    assert role is Role.ADMIN


def test_admin_uses_default_role_on_empty_choice() -> None:
    role = _resolve_enroll_role(
        operator=_operator(Role.ADMIN),
        is_first=False,
        face_config=FaceAuthConfig(default_role=Role.VIEWER),
        reader=lambda _prompt: "",
    )

    assert role is Role.VIEWER


def test_admin_can_enroll_admin() -> None:
    role = _resolve_enroll_role(
        operator=_operator(Role.ADMIN),
        is_first=False,
        face_config=FaceAuthConfig(),
        reader=lambda _prompt: "admin",
    )

    assert role is Role.ADMIN


def test_admin_invalid_choice_falls_back_to_operator() -> None:
    role = _resolve_enroll_role(
        operator=_operator(Role.ADMIN),
        is_first=False,
        face_config=FaceAuthConfig(),
        reader=lambda _prompt: "root",
    )

    assert role is Role.OPERATOR


def test_operator_cannot_enroll_admin() -> None:
    role = _resolve_enroll_role(
        operator=_operator(Role.OPERATOR),
        is_first=False,
        face_config=FaceAuthConfig(),
        reader=lambda _prompt: "admin",
    )

    assert role is None


def test_operator_enrolls_viewer() -> None:
    role = _resolve_enroll_role(
        operator=_operator(Role.OPERATOR),
        is_first=False,
        face_config=FaceAuthConfig(),
        reader=lambda _prompt: "viewer",
    )

    assert role is Role.VIEWER


def test_viewer_cannot_enroll() -> None:
    role = _resolve_enroll_role(
        operator=_operator(Role.VIEWER),
        is_first=False,
        face_config=FaceAuthConfig(),
        reader=lambda _prompt: "",
    )

    assert role is None
