"""Tests del formulario de enrolamiento facial (tkinter falso), sin hardware."""

from __future__ import annotations

import logging
import tkinter
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar, cast

import pytest

from recognizer.cli import face_enroll_gui, menu_gui
from recognizer.cli.face_enroll_gui import run_enroll_form
from recognizer.core.constants import (
    FACE_ENROLL_NAME_PROMPT,
    FACE_ENROLL_NATIONAL_ID_PROMPT,
    FACE_ENROLL_PASSWORD_CONFIRM_PROMPT,
    FACE_ENROLL_PASSWORD_PROMPT,
    FACE_ENROLL_ROLE_PROMPT,
)
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.domain.identity import Identity, Role
from recognizer.core.ports.identity_provider import IdentityProvider

REQUEST = AppRunRequest(config_path=Path("config.yaml"))
TEST_LOGGER = logging.getLogger("recognizer.menu.face.enroll.test")


class FakeToplevel:
    """Doble de tkinter.Toplevel sin display."""

    instances: ClassVar[list[FakeToplevel]] = []

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.titles: list[str] = []
        self.protocols: dict[str, Callable[[], None]] = {}
        self.bindings: dict[str, Callable[..., None]] = {}
        self.withdraw_calls = 0
        self.deiconify_calls = 0
        self.destroy_calls = 0
        self.wait_window_calls = 0
        FakeToplevel.instances.append(self)

    def title(self, name: str) -> None:
        self.titles.append(name)

    def configure(self, *_args: object, **_kwargs: object) -> None:
        pass

    def withdraw(self) -> None:
        self.withdraw_calls += 1

    def deiconify(self) -> None:
        self.deiconify_calls += 1

    def destroy(self) -> None:
        self.destroy_calls += 1

    def protocol(self, name: str, func: Callable[[], None]) -> None:
        self.protocols[name] = func

    def bind(self, sequence: str, func: Callable[..., None]) -> None:
        self.bindings[sequence] = func

    def wait_window(self, _window: object = None) -> None:
        self.wait_window_calls += 1


class _WidgetBase:
    """Widget falso: pack/bind/configure no-op."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.bindings: dict[str, Callable[..., object]] = {}
        self.packed = False

    def pack(self, *_args: object, **_kwargs: object) -> None:
        self.packed = True

    def pack_forget(self) -> None:
        self.packed = False

    def bind(self, sequence: str, func: Callable[..., object]) -> None:
        self.bindings[sequence] = func

    def configure(self, *_args: object, **_kwargs: object) -> None:
        text = _kwargs.get("text")
        if text is not None and hasattr(self, "text"):
            self.text = str(text)

    def focus_set(self) -> None:
        pass


class FakeFrame(_WidgetBase):
    """Doble de tkinter.Frame."""

    instances: ClassVar[list[FakeFrame]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        FakeFrame.instances.append(self)


class FakeLabel(_WidgetBase):
    """Doble de tkinter.Label con texto."""

    instances: ClassVar[list[FakeLabel]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.text = str(kwargs.get("text", ""))
        FakeLabel.instances.append(self)


class FakeButton(_WidgetBase):
    """Doble de tkinter.Button que registra texto y comando."""

    instances: ClassVar[list[FakeButton]] = []

    def __init__(
        self,
        *_args: object,
        text: str = "",
        command: Callable[[], None] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(*_args, **kwargs)
        self.text = text
        self.command = command
        FakeButton.instances.append(self)


class FakeEntry(_WidgetBase):
    """Doble de tkinter.Entry con texto programable."""

    instances: ClassVar[list[FakeEntry]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._value = ""
        FakeEntry.instances.append(self)

    def get(self) -> str:
        return self._value

    def set_text(self, value: str) -> None:
        self._value = value


class FakeStringVar:
    """Doble de tkinter.StringVar con get/set."""

    instances: ClassVar[list[FakeStringVar]] = []

    def __init__(self, value: str = "") -> None:
        self._value = value
        FakeStringVar.instances.append(self)

    def get(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        self._value = value


class FakeOptionMenu(_WidgetBase):
    """Doble de tkinter.OptionMenu: registra las opciones ofrecidas."""

    instances: ClassVar[list[FakeOptionMenu]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.options: tuple[str, ...] = tuple(str(item) for item in args[2:])
        FakeOptionMenu.instances.append(self)


class FakeProvider:
    """Doble de IdentityProvider con rol configurable."""

    def __init__(self, role: Role = Role.ADMIN) -> None:
        self._identity = Identity(face_id="F-0001", name="Ada", role=role, authenticated_at="hoy")

    def current_identity(self) -> Identity:
        return self._identity

    def require_role(self, *_roles: Role) -> Identity:
        return self._identity

    def refresh(self) -> Identity:
        return self._identity


def _install_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeToplevel.instances.clear()
    FakeFrame.instances.clear()
    FakeLabel.instances.clear()
    FakeButton.instances.clear()
    FakeEntry.instances.clear()
    FakeStringVar.instances.clear()
    FakeOptionMenu.instances.clear()
    monkeypatch.setattr(tkinter, "Frame", FakeFrame)
    monkeypatch.setattr(tkinter, "Label", FakeLabel)
    monkeypatch.setattr(tkinter, "Button", FakeButton)
    monkeypatch.setattr(tkinter, "Entry", FakeEntry)
    monkeypatch.setattr(tkinter, "StringVar", FakeStringVar)
    monkeypatch.setattr(tkinter, "OptionMenu", FakeOptionMenu)


def _button_with_text(text: str) -> FakeButton:
    for button in FakeButton.instances:
        if button.text == text:
            return button
    msg = f"no existe el boton {text!r}"
    raise AssertionError(msg)


def _press(command: Callable[[], None] | None) -> None:
    assert command is not None
    command()


def _tk_factory() -> Callable[[], tkinter.Toplevel]:
    return cast("Callable[[], tkinter.Toplevel]", FakeToplevel)


def _run(
    provider: IdentityProvider, *, enroll_runner: face_enroll_gui.EnrollRunner | None = None
) -> int:
    return run_enroll_form(
        REQUEST,
        tk_factory=_tk_factory(),
        identity_provider=provider,
        enroll_runner=enroll_runner,
        logger=TEST_LOGGER,
    )


def _labels() -> list[str]:
    return [label.text for label in FakeLabel.instances]


def test_admin_offers_all_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)

    assert _run(cast("IdentityProvider", FakeProvider(Role.ADMIN))) == 0

    assert FakeOptionMenu.instances[0].options == ("admin", "operator", "viewer")


def test_operator_offers_two_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)

    _run(cast("IdentityProvider", FakeProvider(Role.OPERATOR)))

    assert FakeOptionMenu.instances[0].options == ("operator", "viewer")


def test_first_face_limits_roles_to_admin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from recognizer.adapters.file_face_repository import FileFaceRepository
    from recognizer.adapters.file_identity_provider import FileIdentityProvider

    _install_fakes(monkeypatch)
    store = tmp_path / "faces"
    provider = FileIdentityProvider(store, FileFaceRepository(store))

    _run(cast("IdentityProvider", provider))

    assert FakeOptionMenu.instances[0].options == ("admin",)
    assert face_enroll_gui.ENROLL_FIRST_NOTE_TEXT in _labels()


def test_viewer_without_permission_shows_notice(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)

    _run(cast("IdentityProvider", FakeProvider(Role.VIEWER)))

    assert FakeOptionMenu.instances == []
    assert face_enroll_gui.ENROLL_NO_PERMISSION_TEXT in _labels()


def test_enroll_calls_runner_with_form_values(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    seen: list[list[str]] = []

    def fake_enroll(request: AppRunRequest, *, reader: Callable[[str], str] | None = None) -> int:
        del request
        assert reader is not None
        seen.append(
            [
                reader(FACE_ENROLL_NAME_PROMPT),
                reader(FACE_ENROLL_ROLE_PROMPT),
                reader(FACE_ENROLL_NATIONAL_ID_PROMPT),
                reader(FACE_ENROLL_PASSWORD_PROMPT),
                reader(FACE_ENROLL_PASSWORD_CONFIRM_PROMPT),
            ]
        )
        return 0

    _run(cast("IdentityProvider", FakeProvider(Role.ADMIN)), enroll_runner=fake_enroll)
    FakeEntry.instances[0].set_text("Ada")
    FakeStringVar.instances[0].set("operator")
    FakeEntry.instances[1].set_text("12.345.678")
    FakeEntry.instances[2].set_text("clave1")
    FakeEntry.instances[3].set_text("clave1")
    _press(_button_with_text(face_enroll_gui.ENROLL_TEXT).command)

    assert seen == [["Ada", "operator", "12345678", "clave1", "clave1"]]
    window = FakeToplevel.instances[0]
    assert window.withdraw_calls == 1
    assert window.deiconify_calls == 1
    assert window.destroy_calls == 1


def _error_texts() -> list[str]:
    return [label.text for label in FakeLabel.instances]


def test_empty_dni_shows_error_and_does_not_call_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fakes(monkeypatch)
    calls: list[AppRunRequest] = []

    def fake_enroll(request: AppRunRequest, *, reader: Callable[[str], str] | None = None) -> int:
        del reader
        calls.append(request)
        return 0

    _run(cast("IdentityProvider", FakeProvider(Role.ADMIN)), enroll_runner=fake_enroll)
    FakeEntry.instances[0].set_text("Ada")
    FakeEntry.instances[2].set_text("clave1")
    FakeEntry.instances[3].set_text("clave1")
    _press(_button_with_text(face_enroll_gui.ENROLL_TEXT).command)

    assert calls == []
    assert FakeToplevel.instances[0].destroy_calls == 0
    assert face_enroll_gui.ENROLL_EMPTY_NATIONAL_ID_MESSAGE in _error_texts()


def test_invalid_dni_shows_error_and_does_not_call_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fakes(monkeypatch)
    calls: list[AppRunRequest] = []

    def fake_enroll(request: AppRunRequest, *, reader: Callable[[str], str] | None = None) -> int:
        del reader
        calls.append(request)
        return 0

    _run(cast("IdentityProvider", FakeProvider(Role.ADMIN)), enroll_runner=fake_enroll)
    FakeEntry.instances[0].set_text("Ada")
    FakeEntry.instances[1].set_text("ABC")
    FakeEntry.instances[2].set_text("clave1")
    FakeEntry.instances[3].set_text("clave1")
    _press(_button_with_text(face_enroll_gui.ENROLL_TEXT).command)

    assert calls == []
    assert FakeToplevel.instances[0].destroy_calls == 0
    assert any("DNI" in text for text in _error_texts())


def test_duplicate_dni_shows_error_and_does_not_call_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from recognizer.adapters.file_face_repository import FileFaceRepository
    from recognizer.adapters.file_identity_provider import FileIdentityProvider
    from recognizer.core.domain.face import EnrolledFace

    _install_fakes(monkeypatch)
    store = tmp_path / "faces"
    admin = EnrolledFace(
        face_id="F-0001",
        name="Ada",
        embedding=(1.0, 0.0),
        samples=5,
        created_at="2026-09-19T00:00:00+00:00",
        role=Role.ADMIN,
        national_id="12345678",
    )
    FileFaceRepository(store).save(admin)
    provider = FileIdentityProvider(store, FileFaceRepository(store))
    provider.write_session(admin)
    calls: list[AppRunRequest] = []

    def fake_enroll(request: AppRunRequest, *, reader: Callable[[str], str] | None = None) -> int:
        del reader
        calls.append(request)
        return 0

    _run(cast("IdentityProvider", provider), enroll_runner=fake_enroll)
    FakeEntry.instances[0].set_text("Bo")
    FakeEntry.instances[1].set_text("12345678")
    FakeEntry.instances[2].set_text("clave1")
    FakeEntry.instances[3].set_text("clave1")
    _press(_button_with_text(face_enroll_gui.ENROLL_TEXT).command)

    assert calls == []
    assert FakeToplevel.instances[0].destroy_calls == 0
    assert face_enroll_gui.ENROLL_DUPLICATE_NATIONAL_ID_MESSAGE in _error_texts()


def test_empty_name_does_not_call_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    calls: list[AppRunRequest] = []

    def fake_enroll(request: AppRunRequest, *, reader: Callable[[str], str] | None = None) -> int:
        del reader
        calls.append(request)
        return 0

    _run(cast("IdentityProvider", FakeProvider(Role.ADMIN)), enroll_runner=fake_enroll)
    _press(_button_with_text(face_enroll_gui.ENROLL_TEXT).command)

    assert calls == []
    assert FakeToplevel.instances[0].destroy_calls == 0


def test_close_paths_return_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)

    assert _run(cast("IdentityProvider", FakeProvider(Role.ADMIN))) == 0
    window = FakeToplevel.instances[0]
    assert window.titles == [face_enroll_gui.ENROLL_WINDOW_TITLE]
    assert menu_gui.EVENT_CLOSE_WINDOW in window.protocols
    window.protocols[menu_gui.EVENT_CLOSE_WINDOW]()
    window.bindings[menu_gui.EVENT_ESCAPE](None)
    _press(_button_with_text(face_enroll_gui.ENROLL_BACK_TEXT).command)

    assert window.destroy_calls == 3
