"""Tests del submenu facial grafico y del selector de camara, sin hardware.

El modulo `face_menu_gui` resuelve los widgets como atributos de `tkinter` en
tiempo de llamada, asi que basta con parchearlos e inyectar `FakeToplevel` via
`tk_factory`. El selector de camara de `menu_gui` se prueba con un enumerador
falso (sin OpenCV) y el submenu facial con runners falsos.
"""

from __future__ import annotations

import logging
import tkinter
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar, cast

import pytest

from recognizer.cli import face_menu_gui, menu, menu_gui
from recognizer.cli.face_adapters import allowed_roles
from recognizer.cli.face_menu_gui import run_face_submenu
from recognizer.core.config import AppsConfig
from recognizer.core.domain.app import AppCatalog, AppId, AppRunRequest
from recognizer.core.domain.camera import CameraInfo
from recognizer.core.domain.identity import Identity, Role, anonymous_identity
from recognizer.core.ports.camera_discovery import CameraEnumerator
from recognizer.core.ports.identity_provider import IdentityProvider

REQUEST = AppRunRequest(config_path=Path("config.yaml"))
TEST_LOGGER = logging.getLogger("recognizer.menu.face.test")


class FakeToplevel:
    """Doble de tkinter.Toplevel sin display."""

    instances: ClassVar[list[FakeToplevel]] = []

    def __init__(self) -> None:
        self.titles: list[str] = []
        self.protocols: dict[str, Callable[[], None]] = {}
        self.bindings: dict[str, Callable[..., None]] = {}
        self.withdraw_calls = 0
        self.deiconify_calls = 0
        self.destroy_calls = 0
        self.mainloop_calls = 0
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

    def mainloop(self) -> None:
        self.mainloop_calls += 1

    def wait_window(self, _window: object = None) -> None:
        self.wait_window_calls += 1


class _WidgetBase:
    """Comportamiento comun de los widgets falsos: pack/bind/configure no-op."""

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
        image = _kwargs.get("image")
        if image is not None and hasattr(self, "image"):
            self.image = image

    def focus_set(self) -> None:
        pass

    def destroy(self) -> None:
        self.packed = False


class FakeFrame(_WidgetBase):
    """Doble de tkinter.Frame sin display."""

    instances: ClassVar[list[FakeFrame]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        FakeFrame.instances.append(self)


class FakeLabel(_WidgetBase):
    """Doble de tkinter.Label sin display."""

    instances: ClassVar[list[FakeLabel]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.text = str(kwargs.get("text", ""))
        self.image: object | None = None
        FakeLabel.instances.append(self)


class FakePhotoImage(_WidgetBase):
    """Doble de tkinter.PhotoImage (no lee ningun archivo)."""

    instances: ClassVar[list[FakePhotoImage]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        FakePhotoImage.instances.append(self)


class FakeTreeview(_WidgetBase):
    """Doble de tkinter.ttk.Treeview: filas en memoria y seleccion programable."""

    instances: ClassVar[list[FakeTreeview]] = []

    def __init__(self, *args: object, columns: tuple[str, ...] = (), **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.columns = tuple(columns)
        self.rows: dict[str, tuple[object, ...]] = {}
        self.headings: dict[str, str] = {}
        self.column_config: dict[str, dict[str, object]] = {}
        self._selection: list[str] = []
        FakeTreeview.instances.append(self)

    def heading(self, key: str, *, text: str = "", **_kwargs: object) -> None:
        self.headings[key] = text

    def column(self, key: str, **kwargs: object) -> None:
        self.column_config[key] = kwargs

    def insert(self, _parent: str, _index: str, *, iid: str, values: object) -> None:
        self.rows[iid] = tuple(values)  # type: ignore[arg-type]

    def get_children(self) -> tuple[str, ...]:
        return tuple(self.rows)

    def delete(self, item: str) -> None:
        self.rows.pop(item, None)

    def selection(self) -> tuple[str, ...]:
        return tuple(self._selection)

    def set_selection(self, items: list[str]) -> None:
        self._selection = list(items)

    def yview(self, *_args: object) -> None:
        pass


class FakeScrollbar(_WidgetBase):
    """Doble de tkinter.ttk.Scrollbar."""

    instances: ClassVar[list[FakeScrollbar]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        FakeScrollbar.instances.append(self)

    def set(self, *_args: object) -> None:
        pass


class FakeMessagebox:
    """Doble de tkinter.messagebox con respuesta programable a askyesno."""

    answer: ClassVar[bool] = True
    calls: ClassVar[list[tuple[str, str]]] = []

    @classmethod
    def askyesno(cls, title: str, message: str, **_kwargs: object) -> bool:
        cls.calls.append((title, message))
        return cls.answer


class FakeTtk:
    """Doble del submodulo tkinter.ttk con los widgets usados por los paneles."""

    Treeview = FakeTreeview
    Scrollbar = FakeScrollbar


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

    def insert_text(self, value: str) -> None:
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


class FakeEnumerator:
    """Doble de CameraEnumerator con dos camaras (indices 0 y 2)."""

    def __init__(self) -> None:
        self.calls = 0

    def list_cameras(self) -> tuple[CameraInfo, ...]:
        self.calls += 1
        return (CameraInfo(index=0, label="Cámara 0"), CameraInfo(index=2, label="Cámara 2"))


def _install_face_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Limpia e instala los fakes del submenu facial en tkinter."""
    FakeToplevel.instances.clear()
    FakeFrame.instances.clear()
    FakeLabel.instances.clear()
    FakeButton.instances.clear()
    FakeEntry.instances.clear()
    FakeStringVar.instances.clear()
    FakeOptionMenu.instances.clear()
    FakePhotoImage.instances.clear()
    FakeTreeview.instances.clear()
    FakeScrollbar.instances.clear()
    FakeMessagebox.answer = True
    FakeMessagebox.calls.clear()
    monkeypatch.setattr(tkinter, "Frame", FakeFrame)
    monkeypatch.setattr(tkinter, "Label", FakeLabel)
    monkeypatch.setattr(tkinter, "Button", FakeButton)
    monkeypatch.setattr(tkinter, "Entry", FakeEntry)
    monkeypatch.setattr(tkinter, "OptionMenu", FakeOptionMenu)
    monkeypatch.setattr(tkinter, "StringVar", FakeStringVar)
    monkeypatch.setattr(tkinter, "PhotoImage", FakePhotoImage)
    monkeypatch.setattr(tkinter, "ttk", FakeTtk, raising=False)
    monkeypatch.setattr(tkinter, "messagebox", FakeMessagebox, raising=False)


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


def test_allowed_roles_filters_by_operator() -> None:
    assert allowed_roles(is_first=True, role=Role.VIEWER) == (Role.ADMIN,)
    assert allowed_roles(is_first=False, role=Role.ADMIN) == (
        Role.ADMIN,
        Role.OPERATOR,
        Role.VIEWER,
    )
    assert allowed_roles(is_first=False, role=Role.OPERATOR) == (Role.OPERATOR, Role.VIEWER)
    assert allowed_roles(is_first=False, role=Role.VIEWER) == ()


def test_face_submenu_shows_title_and_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_face_fakes(monkeypatch)

    assert (
        run_face_submenu(
            REQUEST,
            tk_factory=_tk_factory(),
            identity_provider=cast("IdentityProvider", FakeProvider(Role.ADMIN)),
            logger=TEST_LOGGER,
        )
        == 0
    )

    window = FakeToplevel.instances[0]
    assert window.titles == [face_menu_gui.FACE_SUBMENU_TITLE]
    assert window.wait_window_calls == 1
    assert window.mainloop_calls == 0
    # El formulario inline ya no vive en el submenu.
    assert FakeOptionMenu.instances == []


def test_face_submenu_does_not_open_enroll_form_until_pressed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_face_fakes(monkeypatch)
    from recognizer.cli import face_enroll_gui

    calls: list[int] = []

    def fake_form(_request: AppRunRequest, **_kwargs: object) -> int:
        calls.append(1)
        return 0

    monkeypatch.setattr(face_enroll_gui, "run_enroll_form", fake_form)

    run_face_submenu(
        REQUEST,
        tk_factory=_tk_factory(),
        identity_provider=cast("IdentityProvider", FakeProvider(Role.ADMIN)),
        logger=TEST_LOGGER,
    )

    # Abrir el submenu no debe abrir el formulario; solo al pulsar Enrolar.
    assert calls == []


def test_face_submenu_session_line_uses_single_session_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_face_fakes(monkeypatch)

    run_face_submenu(
        REQUEST,
        tk_factory=_tk_factory(),
        identity_provider=cast("IdentityProvider", FakeProvider(Role.ADMIN)),
        logger=TEST_LOGGER,
    )

    texts = [label.text for label in FakeLabel.instances]
    assert face_menu_gui.FACE_SESSION_TEMPLATE.format(name="Ada", role="admin") in texts


def test_face_submenu_viewer_hides_enroll(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_face_fakes(monkeypatch)

    run_face_submenu(
        REQUEST,
        tk_factory=_tk_factory(),
        identity_provider=cast("IdentityProvider", FakeProvider(Role.VIEWER)),
        logger=TEST_LOGGER,
    )

    assert _button_with_text(face_menu_gui.FACE_ENROLL_TEXT).packed is False
    assert _button_with_text(face_menu_gui.FACE_MY_ACCESS_TEXT).packed is True


def test_face_submenu_anonymous_shows_login_card(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_face_fakes(monkeypatch)

    class _AnonymousProvider:
        def current_identity(self) -> Identity:
            return anonymous_identity()

        def require_role(self, *_roles: Role) -> Identity:
            return anonymous_identity()

        def refresh(self) -> Identity:
            return anonymous_identity()

    assert (
        run_face_submenu(
            REQUEST,
            tk_factory=_tk_factory(),
            identity_provider=cast("IdentityProvider", _AnonymousProvider()),
            logger=TEST_LOGGER,
        )
        == 0
    )

    assert _button_with_text(face_menu_gui.FACE_ENROLL_TEXT).packed is False
    assert _button_with_text(face_menu_gui.FACE_LOGIN_TEXT).packed is True
    texts = [label.text for label in FakeLabel.instances]
    assert face_menu_gui.FACE_LOGIN_PROMPT in texts


def test_face_submenu_enroll_opens_form(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_face_fakes(monkeypatch)
    from recognizer.cli import face_enroll_gui

    calls: list[dict[str, object]] = []

    def fake_form(_request: AppRunRequest, **kwargs: object) -> int:
        calls.append(kwargs)
        return 0

    monkeypatch.setattr(face_enroll_gui, "run_enroll_form", fake_form)

    def fake_enroll(request: AppRunRequest, *, reader: Callable[[str], str] | None = None) -> int:
        del request, reader
        return 0

    run_face_submenu(
        REQUEST,
        tk_factory=_tk_factory(),
        enroll_runner=fake_enroll,
        identity_provider=cast("IdentityProvider", FakeProvider(Role.ADMIN)),
        logger=TEST_LOGGER,
    )

    _press(_button_with_text(face_menu_gui.FACE_ENROLL_TEXT).command)

    assert len(calls) == 1
    assert calls[0]["enroll_runner"] is not None
    window = FakeToplevel.instances[0]
    assert window.withdraw_calls == 1
    assert window.deiconify_calls == 1


def test_face_submenu_enroll_without_permission_does_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_face_fakes(monkeypatch)
    calls: list[tuple[AppRunRequest, bool]] = []

    def fake_enroll(request: AppRunRequest, *, reader: Callable[[str], str] | None = None) -> int:
        calls.append((request, reader is None))
        return 0

    run_face_submenu(
        REQUEST,
        tk_factory=_tk_factory(),
        enroll_runner=fake_enroll,
        identity_provider=cast("IdentityProvider", FakeProvider(Role.VIEWER)),
        logger=TEST_LOGGER,
    )

    _press(_button_with_text(face_menu_gui.FACE_ENROLL_TEXT).command)

    assert calls == []
    assert FakeToplevel.instances[0].withdraw_calls == 0


def test_face_submenu_login_and_logout_run_without_reader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_face_fakes(monkeypatch)
    logins: list[AppRunRequest] = []
    logouts: list[AppRunRequest] = []

    def fake_login(request: AppRunRequest) -> int:
        logins.append(request)
        return 0

    def fake_logout(request: AppRunRequest) -> int:
        logouts.append(request)
        return 0

    run_face_submenu(
        REQUEST,
        tk_factory=_tk_factory(),
        login_runner=fake_login,
        logout_runner=fake_logout,
        identity_provider=cast("IdentityProvider", FakeProvider(Role.OPERATOR)),
        logger=TEST_LOGGER,
    )

    _press(_button_with_text(face_menu_gui.FACE_LOGIN_TEXT).command)
    _press(_button_with_text(face_menu_gui.FACE_LOGOUT_TEXT).command)

    assert len(logins) == 1
    assert len(logouts) == 1


def test_face_submenu_close_paths_return_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_face_fakes(monkeypatch)

    assert (
        run_face_submenu(
            REQUEST,
            tk_factory=_tk_factory(),
            identity_provider=cast("IdentityProvider", FakeProvider(Role.ADMIN)),
            logger=TEST_LOGGER,
        )
        == 0
    )

    window = FakeToplevel.instances[0]
    assert menu_gui.EVENT_CLOSE_WINDOW in window.protocols
    assert menu_gui.EVENT_ESCAPE in window.bindings
    window.protocols[menu_gui.EVENT_CLOSE_WINDOW]()
    window.bindings[menu_gui.EVENT_ESCAPE](None)
    _press(_button_with_text(face_menu_gui.FACE_BACK_TEXT).command)
    assert window.destroy_calls == 3


def test_face_submenu_visibility_follows_role_and_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_face_fakes(monkeypatch)

    run_face_submenu(
        REQUEST,
        tk_factory=_tk_factory(),
        identity_provider=cast("IdentityProvider", FakeProvider(Role.ADMIN)),
        logger=TEST_LOGGER,
    )

    assert _button_with_text(face_menu_gui.FACE_ENROLL_TEXT).packed is True
    assert _button_with_text(face_menu_gui.FACE_LOGIN_TEXT).packed is False
    assert _button_with_text(face_menu_gui.FACE_LOGOUT_TEXT).packed is True
    assert _button_with_text(face_menu_gui.FACE_USERS_TEXT).packed is True
    assert _button_with_text(face_menu_gui.FACE_ACCESS_TEXT).packed is True
    assert _button_with_text(face_menu_gui.FACE_MY_ACCESS_TEXT).packed is False


def test_face_submenu_non_admin_sees_my_access_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_face_fakes(monkeypatch)

    run_face_submenu(
        REQUEST,
        tk_factory=_tk_factory(),
        identity_provider=cast("IdentityProvider", FakeProvider(Role.OPERATOR)),
        logger=TEST_LOGGER,
    )

    assert _button_with_text(face_menu_gui.FACE_USERS_TEXT).packed is False
    assert _button_with_text(face_menu_gui.FACE_ACCESS_TEXT).packed is False
    assert _button_with_text(face_menu_gui.FACE_MY_ACCESS_TEXT).packed is True


def test_face_submenu_admin_opens_users_and_access_panels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_face_fakes(monkeypatch)
    from recognizer.cli import face_access_gui, face_users_gui

    users_calls: list[dict[str, object]] = []
    access_calls: list[dict[str, object]] = []

    def fake_users(_request: AppRunRequest, **kwargs: object) -> int:
        users_calls.append(kwargs)
        return 0

    def fake_access(_request: AppRunRequest, **kwargs: object) -> int:
        access_calls.append(kwargs)
        return 0

    monkeypatch.setattr(face_users_gui, "run_users_panel", fake_users)
    monkeypatch.setattr(face_access_gui, "run_access_panel", fake_access)

    run_face_submenu(
        REQUEST,
        tk_factory=_tk_factory(),
        identity_provider=cast("IdentityProvider", FakeProvider(Role.ADMIN)),
        logger=TEST_LOGGER,
    )

    _press(_button_with_text(face_menu_gui.FACE_USERS_TEXT).command)
    _press(_button_with_text(face_menu_gui.FACE_ACCESS_TEXT).command)

    assert len(users_calls) == 1
    assert users_calls[0]["identity_provider"] is not None
    assert len(access_calls) == 1
    assert access_calls[0]["show_photos"] is True


def test_face_submenu_non_admin_my_access_hides_photos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_face_fakes(monkeypatch)
    from recognizer.cli import face_access_gui

    access_calls: list[dict[str, object]] = []

    def fake_access(_request: AppRunRequest, **kwargs: object) -> int:
        access_calls.append(kwargs)
        return 0

    monkeypatch.setattr(face_access_gui, "run_access_panel", fake_access)

    run_face_submenu(
        REQUEST,
        tk_factory=_tk_factory(),
        identity_provider=cast("IdentityProvider", FakeProvider(Role.OPERATOR)),
        logger=TEST_LOGGER,
    )

    _press(_button_with_text(face_menu_gui.FACE_MY_ACCESS_TEXT).command)

    assert len(access_calls) == 1
    assert access_calls[0]["show_photos"] is False


class FakeMenuRoot:
    """Doble de la raiz Tk del menu principal, sin display real."""

    on_mainloop: ClassVar[Callable[..., None] | None] = None
    instances: ClassVar[list[FakeMenuRoot]] = []

    def __init__(self) -> None:
        self.protocols: dict[str, Callable[[], None]] = {}
        self.bindings: dict[str, Callable[..., None]] = {}
        self.withdraw_calls = 0
        self.deiconify_calls = 0
        FakeMenuRoot.instances.append(self)

    def title(self, _name: str) -> None:
        pass

    def configure(self, *_args: object, **_kwargs: object) -> None:
        pass

    def geometry(self, _value: str) -> None:
        pass

    def minsize(self, *_args: object) -> None:
        pass

    def resizable(self, *_args: object) -> None:
        pass

    def winfo_screenwidth(self) -> int:
        return 1920

    def winfo_screenheight(self) -> int:
        return 1080

    def withdraw(self) -> None:
        self.withdraw_calls += 1

    def deiconify(self) -> None:
        self.deiconify_calls += 1

    def destroy(self) -> None:
        pass

    def protocol(self, name: str, func: Callable[[], None]) -> None:
        self.protocols[name] = func

    def bind(self, sequence: str, func: Callable[..., None]) -> None:
        self.bindings[sequence] = func

    def mainloop(self) -> None:
        hook = FakeMenuRoot.on_mainloop
        if hook is not None:
            hook(self)


class FakeMenuButton(_WidgetBase):
    """Doble de Button del menu principal: registra texto y comando."""

    instances: ClassVar[list[FakeMenuButton]] = []

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
        FakeMenuButton.instances.append(self)


class FakeMenuCanvas(_WidgetBase):
    """Doble de Canvas del menu principal: ventana embebida no-op."""

    instances: ClassVar[list[FakeMenuCanvas]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        FakeMenuCanvas.instances.append(self)

    def create_window(self, *_args: object, **_kwargs: object) -> int:
        return 1

    def bbox(self, *_args: object) -> tuple[int, int, int, int]:
        return (0, 0, 0, 0)

    def itemconfigure(self, *_args: object, **_kwargs: object) -> None:
        pass

    def yview(self, *_args: object) -> None:
        pass

    def yview_scroll(self, _number: int, _what: str) -> None:
        pass


class FakeMenuScrollbar(_WidgetBase):
    """Doble de Scrollbar del menu principal."""

    instances: ClassVar[list[FakeMenuScrollbar]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        FakeMenuScrollbar.instances.append(self)

    def set(self, *_args: object) -> None:
        pass


def _install_menu_fakes(monkeypatch: pytest.MonkeyPatch) -> type[FakeMenuRoot]:
    """Instala los fakes del menu principal en tkinter (sin display)."""
    FakeMenuRoot.on_mainloop = None
    FakeMenuRoot.instances.clear()
    FakeFrame.instances.clear()
    FakeLabel.instances.clear()
    FakeMenuButton.instances.clear()
    FakeMenuCanvas.instances.clear()
    FakeMenuScrollbar.instances.clear()
    monkeypatch.setattr(tkinter, "Frame", FakeFrame)
    monkeypatch.setattr(tkinter, "Label", FakeLabel)
    monkeypatch.setattr(tkinter, "Button", FakeMenuButton)
    monkeypatch.setattr(tkinter, "Canvas", FakeMenuCanvas)
    monkeypatch.setattr(tkinter, "Scrollbar", FakeMenuScrollbar)
    monkeypatch.setattr(menu_gui, "display_font_paths", lambda: ())
    monkeypatch.setattr(menu_gui, "desktop_icon_path", lambda: None)
    monkeypatch.setattr(menu_gui, "desktop_logo_path", lambda: None)
    return FakeMenuRoot


def _menu_button_with_text(text: str) -> FakeMenuButton:
    for button in FakeMenuButton.instances:
        if button.text == text:
            return button
    msg = f"no existe el boton {text!r}"
    raise AssertionError(msg)


def _menu_app_button(number: int) -> FakeMenuButton:
    prefix = f"{number}. "
    for button in FakeMenuButton.instances:
        if button.text.startswith(prefix):
            return button
    msg = f"no existe el boton de la app {number}"
    raise AssertionError(msg)


def _menu_press(command: Callable[[], None] | None) -> None:
    assert command is not None
    command()


def test_menu_opens_face_submenu_instead_of_direct_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_root_cls = _install_menu_fakes(monkeypatch)
    monkeypatch.setattr(menu, "resolve_runner", lambda _app_id: None)
    seen: list[AppRunRequest] = []

    def fake_submenu(request: AppRunRequest, **_kwargs: object) -> int:
        seen.append(request)
        return 0

    monkeypatch.setattr("recognizer.cli.face_menu_gui.run_face_submenu", fake_submenu)
    face_row = next(
        row
        for row in menu_gui.build_menu_rows(AppCatalog(), AppsConfig())
        if row.app_id is AppId.FACE_AUTH
    )
    fake_root_cls.on_mainloop = lambda _root: _menu_press(_menu_app_button(face_row.number).command)

    assert (
        menu_gui.run_gui_menu(
            request=REQUEST,
            apps_config=AppsConfig(),
            logger=TEST_LOGGER,
            tk_factory=cast("Callable[[], tkinter.Tk]", fake_root_cls),
        )
        == 0
    )

    assert len(seen) == 1


def test_menu_camera_selector_detects_cycles_and_propagates_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_root_cls = _install_menu_fakes(monkeypatch)
    enumerator = FakeEnumerator()
    seen: list[AppRunRequest] = []

    def fake_runner(request: AppRunRequest) -> int:
        seen.append(request)
        return 0

    monkeypatch.setattr(menu, "resolve_runner", lambda _app_id: fake_runner)

    def _interact(_root: FakeMenuRoot) -> None:
        _menu_press(_menu_button_with_text(menu_gui.GUI_CAMERA_DETECT_TEXT).command)
        # Detectar selecciona la primera (0) y refresca la etiqueta del ciclo.
        _menu_press(_menu_button_with_text("0").command)
        _menu_press(_menu_app_button(1).command)

    fake_root_cls.on_mainloop = _interact

    assert (
        menu_gui.run_gui_menu(
            request=REQUEST,
            apps_config=AppsConfig(),
            logger=TEST_LOGGER,
            tk_factory=cast("Callable[[], tkinter.Tk]", fake_root_cls),
            camera_enumerator=cast("CameraEnumerator", enumerator),
        )
        == 0
    )

    assert enumerator.calls == 1
    assert seen
    assert seen[0].device == 2
