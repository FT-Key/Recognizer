"""Tests del gating por rol en el menú (consola y gráfico), sin hardware."""

import logging
from collections.abc import Callable
from pathlib import Path

import pytest

from recognizer.adapters.file_face_repository import FileFaceRepository
from recognizer.adapters.file_identity_provider import FileIdentityProvider
from recognizer.cli import menu
from recognizer.cli.menu import (
    LABEL_NO_PERMISSION,
    _build_policy,
    _identity_from_config,
    render_catalog,
    run_menu,
)
from recognizer.cli.menu_gui import build_menu_rows
from recognizer.core.config import AppConfig, AppsConfig, FaceAuthConfig
from recognizer.core.domain.app import AppCatalog, AppId, AppRunRequest
from recognizer.core.domain.face import EnrolledFace
from recognizer.core.domain.identity import (
    AllowAllPolicy,
    Identity,
    PolicyEngine,
    Role,
)
from recognizer.core.errors import AuthError

REQUEST = AppRunRequest(config_path=Path("config.yaml"))
TEST_LOGGER = logging.getLogger("recognizer.menu.identity.test")
AUTH_AT = "2026-09-19T12:00:00+00:00"


class _FakeProvider:
    """Doble del puerto de identidad con una identidad fija."""

    def __init__(self, identity: Identity) -> None:
        self._identity = identity

    def current_identity(self) -> Identity:
        return self._identity

    def require_role(self, *roles: Role) -> Identity:
        if self._identity.role not in roles:
            msg = f"Sin permiso (actual: {self._identity.role.value})."
            raise AuthError(msg)
        return self._identity

    def refresh(self) -> Identity:
        return self._identity


def _identity(role: Role) -> Identity:
    return Identity(face_id="F-0001", name="Ada", role=role, authenticated_at=AUTH_AT)


def _scripted(values: list[str]) -> Callable[[str], str]:
    iterator = iter(values)

    def reader(_prompt: str) -> str:
        return next(iterator)

    return reader


def _row_line(text: str, title: str) -> str:
    for line in text.splitlines():
        if title in line:
            return line
    raise AssertionError(f"fila no encontrada: {title}")


def test_render_catalog_viewer_marks_restricted_with_no_permission() -> None:
    text = render_catalog(
        AppCatalog(),
        AppsConfig(),
        identity=_identity(Role.VIEWER),
        policy=PolicyEngine(),
    )

    assert LABEL_NO_PERMISSION not in _row_line(text, "Reconocimiento de gestos")
    assert LABEL_NO_PERMISSION not in _row_line(text, "Postura ergon")
    assert LABEL_NO_PERMISSION in _row_line(text, "Contador de personas")
    assert LABEL_NO_PERMISSION in _row_line(text, "Anti-intrusos")
    assert LABEL_NO_PERMISSION in _row_line(text, "Reconocimiento facial")


def test_render_catalog_admin_has_no_denied_label() -> None:
    text = render_catalog(
        AppCatalog(),
        AppsConfig(),
        identity=_identity(Role.ADMIN),
        policy=PolicyEngine(),
    )

    assert LABEL_NO_PERMISSION not in text


def test_render_catalog_without_policy_keeps_legacy_labels() -> None:
    text = render_catalog(AppCatalog(), AppsConfig())

    assert LABEL_NO_PERMISSION not in text


def test_run_menu_viewer_is_blocked_from_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[AppRunRequest] = []

    def fake_runner(request: AppRunRequest) -> int:
        calls.append(request)
        return 0

    monkeypatch.setattr(menu, "resolve_runner", lambda _app_id: fake_runner)

    result = run_menu(
        request=REQUEST,
        apps_config=AppsConfig(),
        input_fn=_scripted(["2", "0"]),
        logger=TEST_LOGGER,
        identity_provider=_FakeProvider(_identity(Role.VIEWER)),
        policy=PolicyEngine(),
    )

    assert result == 0
    assert calls == []


def test_run_menu_viewer_can_open_gestures(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[AppRunRequest] = []

    def fake_runner(request: AppRunRequest) -> int:
        calls.append(request)
        return 0

    monkeypatch.setattr(menu, "resolve_runner", lambda _app_id: fake_runner)

    run_menu(
        request=REQUEST,
        apps_config=AppsConfig(),
        input_fn=_scripted(["1", "0"]),
        logger=TEST_LOGGER,
        identity_provider=_FakeProvider(_identity(Role.VIEWER)),
        policy=PolicyEngine(),
    )

    assert calls == [REQUEST]


def test_run_menu_admin_can_open_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[AppRunRequest] = []

    def fake_runner(request: AppRunRequest) -> int:
        calls.append(request)
        return 0

    monkeypatch.setattr(menu, "resolve_runner", lambda _app_id: fake_runner)

    run_menu(
        request=REQUEST,
        apps_config=AppsConfig(),
        input_fn=_scripted(["2", "0"]),
        logger=TEST_LOGGER,
        identity_provider=_FakeProvider(_identity(Role.ADMIN)),
        policy=PolicyEngine(),
    )

    assert calls == [REQUEST]


def test_run_menu_allow_all_permits_everything_without_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[AppRunRequest] = []

    def fake_runner(request: AppRunRequest) -> int:
        calls.append(request)
        return 0

    monkeypatch.setattr(menu, "resolve_runner", lambda _app_id: fake_runner)

    run_menu(
        request=REQUEST,
        apps_config=AppsConfig(),
        input_fn=_scripted(["2", "0"]),
        logger=TEST_LOGGER,
        identity_provider=_FakeProvider(
            Identity(face_id="local", name="local", role=Role.ADMIN, authenticated_at="")
        ),
        policy=AllowAllPolicy(),
    )

    assert calls == [REQUEST]


def test_build_menu_rows_viewer_denies_restricted_apps() -> None:
    rows = build_menu_rows(
        AppCatalog(),
        AppsConfig(),
        identity=_identity(Role.VIEWER),
        policy=PolicyEngine(),
    )
    by_id = {row.app_id: row for row in rows if row.app_id is not None}

    assert by_id[AppId.GESTURES].selectable is True
    assert by_id[AppId.POSTURE].selectable is True
    assert by_id[AppId.PEOPLE_COUNTER].denied is True
    assert by_id[AppId.PEOPLE_COUNTER].selectable is False
    assert LABEL_NO_PERMISSION in by_id[AppId.PEOPLE_COUNTER].label
    assert by_id[AppId.FACE_AUTH].denied is True


def test_build_menu_rows_admin_denies_nothing() -> None:
    rows = build_menu_rows(
        AppCatalog(),
        AppsConfig(),
        identity=_identity(Role.ADMIN),
        policy=PolicyEngine(),
    )

    assert all(row.denied is False for row in rows)


def test_build_policy_applies_permissions_override() -> None:
    face_config = FaceAuthConfig(permissions={"gestures": [Role.ADMIN]})
    policy = _build_policy(face_config)

    assert policy.can_launch(_identity(Role.VIEWER), app_id=AppId.GESTURES) is False
    assert policy.can_launch(_identity(Role.ADMIN), app_id=AppId.GESTURES) is True


def test_open_mode_without_session_uses_allow_all(tmp_path: Path) -> None:
    config = AppConfig(
        face_auth=FaceAuthConfig(store_dir=str(tmp_path / "faces"), require_login=False)
    )

    _, policy = _identity_from_config(config)

    assert isinstance(policy, AllowAllPolicy)


def test_login_required_without_session_uses_policy_engine(tmp_path: Path) -> None:
    config = AppConfig(
        face_auth=FaceAuthConfig(store_dir=str(tmp_path / "faces"), require_login=True)
    )

    _, policy = _identity_from_config(config)

    assert isinstance(policy, PolicyEngine)


def test_open_mode_with_session_uses_policy_engine(tmp_path: Path) -> None:
    store = tmp_path / "faces"
    repo = FileFaceRepository(store)
    face = EnrolledFace(
        face_id="F-0001",
        name="Ada",
        embedding=(1.0, 0.0),
        samples=5,
        created_at="2026-09-19T00:00:00+00:00",
        role=Role.OPERATOR,
    )
    repo.save(face)
    FileIdentityProvider(store, repo, session_timeout_seconds=0).write_session(face)
    config = AppConfig(
        face_auth=FaceAuthConfig(
            store_dir=str(store),
            require_login=False,
            session_timeout_seconds=0,
        )
    )

    provider, policy = _identity_from_config(config)

    assert isinstance(policy, PolicyEngine)
    assert provider.current_identity().face_id == "F-0001"
