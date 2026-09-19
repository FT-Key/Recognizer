"""Tests del dominio de identidad y permisos por rol, sin hardware."""

import pytest

from recognizer.core.domain.app import AppCatalog, AppId
from recognizer.core.domain.identity import (
    DEFAULT_PERMISSIONS,
    AllowAllPolicy,
    Identity,
    PolicyEngine,
    Role,
    SessionRecord,
    anonymous_identity,
    normalize_overrides,
    session_expired,
)
from recognizer.core.errors import ConfigError

AUTH_AT = "2026-09-19T12:00:00+00:00"
EXPIRES_AT = "2026-09-19T14:00:00+00:00"
BEFORE_EXPIRY = "2026-09-19T12:00:00+00:00"
AFTER_EXPIRY = "2026-09-19T15:00:00+00:00"


def _identity(role: Role) -> Identity:
    return Identity(face_id="F-0001", name="Ada", role=role, authenticated_at=AUTH_AT)


def _record(expires_at: str) -> SessionRecord:
    return SessionRecord(face_id="F-0001", authenticated_at=AUTH_AT, expires_at=expires_at)


def test_anonymous_identity_is_viewer_without_timestamp() -> None:
    guest = anonymous_identity()

    assert guest.role is Role.VIEWER
    assert guest.authenticated_at == ""
    assert guest.face_id != ""


def test_viewer_only_launches_gestures_and_posture() -> None:
    policy = PolicyEngine()

    assert policy.can_launch(_identity(Role.VIEWER), app_id=AppId.GESTURES) is True
    assert policy.can_launch(_identity(Role.VIEWER), app_id=AppId.POSTURE) is True
    assert policy.can_launch(_identity(Role.VIEWER), app_id=AppId.PEOPLE_COUNTER) is False
    assert policy.can_launch(_identity(Role.VIEWER), app_id=AppId.ANTI_INTRUDER) is False
    assert policy.can_launch(_identity(Role.VIEWER), app_id=AppId.FACE_AUTH) is False
    assert policy.can_launch(_identity(Role.VIEWER), app_id=AppId.PPE_DETECTOR) is False
    assert policy.can_launch(_identity(Role.VIEWER), app_id=AppId.INVENTORY) is False


def test_operator_launches_all_but_training_apps() -> None:
    policy = PolicyEngine()
    operator = _identity(Role.OPERATOR)

    assert policy.can_launch(operator, app_id=AppId.PEOPLE_COUNTER) is True
    assert policy.can_launch(operator, app_id=AppId.ANTI_INTRUDER) is True
    assert policy.can_launch(operator, app_id=AppId.FACE_AUTH) is True
    assert policy.can_launch(operator, app_id=AppId.PPE_DETECTOR) is False
    assert policy.can_launch(operator, app_id=AppId.INVENTORY) is False


def test_admin_launches_everything() -> None:
    policy = PolicyEngine()
    admin = _identity(Role.ADMIN)

    for app_id in AppId:
        assert policy.can_launch(admin, app_id=app_id) is True


def test_visible_apps_keeps_catalog_order_and_hierarchy() -> None:
    policy = PolicyEngine()
    catalog = AppCatalog()

    viewer_apps = policy.visible_apps(_identity(Role.VIEWER), catalog=catalog)
    operator_apps = policy.visible_apps(_identity(Role.OPERATOR), catalog=catalog)
    admin_apps = policy.visible_apps(_identity(Role.ADMIN), catalog=catalog)

    assert tuple(info.app_id for info in viewer_apps) == (AppId.GESTURES, AppId.POSTURE)
    viewer_ids = {info.app_id for info in viewer_apps}
    operator_ids = {info.app_id for info in operator_apps}
    admin_ids = {info.app_id for info in admin_apps}
    assert viewer_ids < operator_ids < admin_ids
    assert len(admin_apps) == len(catalog.apps)


def test_can_enroll_admin_enrolls_any_role() -> None:
    policy = PolicyEngine()
    admin = _identity(Role.ADMIN)

    assert policy.can_enroll(admin, target_role=Role.ADMIN) is True
    assert policy.can_enroll(admin, target_role=Role.OPERATOR) is True
    assert policy.can_enroll(admin, target_role=Role.VIEWER) is True


def test_can_enroll_operator_never_enrolls_admin() -> None:
    policy = PolicyEngine()
    operator = _identity(Role.OPERATOR)

    assert policy.can_enroll(operator, target_role=Role.ADMIN) is False
    assert policy.can_enroll(operator, target_role=Role.OPERATOR) is True
    assert policy.can_enroll(operator, target_role=Role.VIEWER) is True


def test_can_enroll_viewer_and_guest_enroll_nothing() -> None:
    policy = PolicyEngine()

    for identity in (_identity(Role.VIEWER), anonymous_identity()):
        for target in Role:
            assert policy.can_enroll(identity, target_role=target) is False


def test_override_restricts_app_to_admins() -> None:
    merged = dict(DEFAULT_PERMISSIONS)
    merged.update(normalize_overrides({"gestures": [Role.ADMIN]}))
    policy = PolicyEngine(permissions=merged)

    assert policy.can_launch(_identity(Role.VIEWER), app_id=AppId.GESTURES) is False
    assert policy.can_launch(_identity(Role.OPERATOR), app_id=AppId.GESTURES) is False
    assert policy.can_launch(_identity(Role.ADMIN), app_id=AppId.GESTURES) is True


def test_normalize_overrides_rejects_unknown_app() -> None:
    with pytest.raises(ConfigError, match="desconocida"):
        normalize_overrides({"app_fantasma": [Role.ADMIN]})


def test_allow_all_policy_permits_everything() -> None:
    policy = AllowAllPolicy()
    catalog = AppCatalog()

    for role in Role:
        identity = _identity(role)
        for app_id in AppId:
            assert policy.can_launch(identity, app_id=app_id) is True
        for target in Role:
            assert policy.can_enroll(identity, target_role=target) is True

    visible = policy.visible_apps(anonymous_identity(), catalog=catalog)
    assert tuple(info.app_id for info in visible) == tuple(info.app_id for info in catalog.apps)


def test_session_without_expiry_never_expires() -> None:
    assert session_expired(_record(""), now_iso=AFTER_EXPIRY) is False


def test_session_before_expiry_is_valid() -> None:
    assert session_expired(_record(EXPIRES_AT), now_iso=BEFORE_EXPIRY) is False


def test_session_at_or_after_expiry_is_expired() -> None:
    assert session_expired(_record(EXPIRES_AT), now_iso=EXPIRES_AT) is True
    assert session_expired(_record(EXPIRES_AT), now_iso=AFTER_EXPIRY) is True


def test_session_with_corrupt_expiry_is_expired() -> None:
    assert session_expired(_record("no-es-una-fecha"), now_iso=BEFORE_EXPIRY) is True


def test_session_with_corrupt_now_is_expired() -> None:
    assert session_expired(_record(EXPIRES_AT), now_iso="tampoco-es-fecha") is True


def test_session_with_naive_datetimes_uses_utc() -> None:
    record = _record("2026-09-19T14:00:00")

    assert session_expired(record, now_iso="2026-09-19T12:00:00") is False
    assert session_expired(record, now_iso="2026-09-19T15:00:00") is True
