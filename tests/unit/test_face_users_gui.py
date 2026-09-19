"""Tests del panel de usuarios faciales (tkinter falso), sin display ni hardware."""

from __future__ import annotations

import logging
import tkinter
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar, cast

import pytest

from recognizer.cli import face_users_gui, menu_gui
from recognizer.cli.face_users_gui import run_users_panel
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.domain.credentials import hash_password, verify_password
from recognizer.core.domain.face import EnrolledFace, FaceEmbedding
from recognizer.core.domain.identity import Identity, Role
from recognizer.core.ports.face_repository import FaceRepository
from recognizer.core.ports.identity_provider import IdentityProvider

REQUEST = AppRunRequest(config_path=Path("config.yaml"))
TEST_LOGGER = logging.getLogger("recognizer.menu.face.users.test")
EMBEDDING: FaceEmbedding = (1.0, 0.0)
CREATED_AT = "2026-09-19T00:00:00+00:00"
PREVIEW_PATH = Path("previews") / "F-0001.png"


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
        self.grab_calls = 0
        FakeToplevel.instances.append(self)

    def title(self, name: str) -> None:
        self.titles.append(name)

    def configure(self, *_args: object, **_kwargs: object) -> None:
        pass

    def grab_set(self) -> None:
        self.grab_calls += 1

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
    """Widget falso: pack/pack_forget/bind/configure no-op."""

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


class FakeFrame(_WidgetBase):
    """Doble de tkinter.Frame."""

    instances: ClassVar[list[FakeFrame]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        FakeFrame.instances.append(self)


class FakeLabel(_WidgetBase):
    """Doble de tkinter.Label con texto e imagen."""

    instances: ClassVar[list[FakeLabel]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.text = str(kwargs.get("text", ""))
        self.image: object | None = None
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

    def insert(self, _index: int, value: str) -> None:
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
    """Doble de tkinter.OptionMenu."""

    instances: ClassVar[list[FakeOptionMenu]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.options: tuple[str, ...] = tuple(str(item) for item in args[2:])
        FakeOptionMenu.instances.append(self)


class FakePhotoImage(_WidgetBase):
    """Doble de tkinter.PhotoImage (no lee ningun archivo)."""

    instances: ClassVar[list[FakePhotoImage]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        FakePhotoImage.instances.append(self)


class FakeTreeview(_WidgetBase):
    """Doble de ttk.Treeview con filas en memoria y seleccion programable."""

    instances: ClassVar[list[FakeTreeview]] = []

    def __init__(self, *args: object, columns: tuple[str, ...] = (), **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.columns = tuple(columns)
        self.rows: dict[str, tuple[object, ...]] = {}
        self._selection: list[str] = []
        FakeTreeview.instances.append(self)

    def heading(self, *_args: object, **_kwargs: object) -> None:
        pass

    def column(self, *_args: object, **_kwargs: object) -> None:
        pass

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
    """Doble de ttk.Scrollbar."""

    instances: ClassVar[list[FakeScrollbar]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        FakeScrollbar.instances.append(self)

    def set(self, *_args: object) -> None:
        pass


class FakeTtk:
    """Doble del submodulo tkinter.ttk."""

    Treeview = FakeTreeview
    Scrollbar = FakeScrollbar


class FakeMessagebox:
    """Doble de tkinter.messagebox con respuesta programable."""

    answer: ClassVar[bool] = True
    calls: ClassVar[list[tuple[str, str]]] = []

    @classmethod
    def askyesno(cls, title: str, message: str, **_kwargs: object) -> bool:
        cls.calls.append((title, message))
        return cls.answer


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


class FakeFaceRepository:
    """Doble en memoria del puerto FaceRepository."""

    def __init__(
        self,
        faces: tuple[EnrolledFace, ...] = (),
        previews: dict[str, Path] | None = None,
    ) -> None:
        self.faces = {face.face_id: face for face in faces}
        self.previews = dict(previews or {})
        self.updated: list[EnrolledFace] = []
        self.deleted: list[str] = []

    def next_id(self) -> str:
        return "F-9999"

    def save(self, face: EnrolledFace) -> None:
        self.faces[face.face_id] = face

    def update(self, face: EnrolledFace) -> None:
        self.updated.append(face)
        self.faces[face.face_id] = face

    def delete(self, face_id: str) -> None:
        self.deleted.append(face_id)
        self.faces.pop(face_id, None)

    def list_all(self) -> tuple[EnrolledFace, ...]:
        return tuple(sorted(self.faces.values(), key=lambda face: face.face_id))

    def find_by_id(self, face_id: str) -> EnrolledFace | None:
        return self.faces.get(face_id)

    def find_by_name(self, name: str) -> tuple[EnrolledFace, ...]:
        return tuple(face for face in self.faces.values() if face.name == name)

    def save_preview(self, *, face_id: str, image: bytes) -> str:  # noqa: ARG002
        self.previews[face_id] = Path(f"{face_id}.png")
        return f"{face_id}.png"

    def preview_path(self, face_id: str) -> Path | None:
        return self.previews.get(face_id)


def _face(
    face_id: str = "F-0001",
    name: str = "Ada",
    role: Role = Role.OPERATOR,
    *,
    password_hash: str = "",
) -> EnrolledFace:
    return EnrolledFace(
        face_id=face_id,
        name=name,
        embedding=EMBEDDING,
        samples=5,
        created_at=CREATED_AT,
        role=role,
        password_hash=password_hash,
    )


def _install_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
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
    monkeypatch.setattr(tkinter, "StringVar", FakeStringVar)
    monkeypatch.setattr(tkinter, "OptionMenu", FakeOptionMenu)
    monkeypatch.setattr(tkinter, "PhotoImage", FakePhotoImage)
    monkeypatch.setattr(tkinter, "Toplevel", FakeToplevel)
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


def _run(role: Role, repository: FaceRepository) -> int:
    return run_users_panel(
        REQUEST,
        tk_factory=_tk_factory(),
        repository=repository,
        identity_provider=cast("IdentityProvider", FakeProvider(role)),
        logger=TEST_LOGGER,
    )


def test_non_admin_does_not_open_panel(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)

    result = _run(Role.VIEWER, FakeFaceRepository((_face(),)))

    assert result == 1
    assert FakeToplevel.instances == []


def test_admin_lists_all_faces(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    repo = FakeFaceRepository((_face("F-0001", "Ada"), _face("F-0002", "Bo")))

    result = _run(Role.ADMIN, repo)

    assert result == 0
    tree = FakeTreeview.instances[0]
    assert tuple(tree.rows) == ("F-0001", "F-0002")
    assert tree.rows["F-0001"][1] == "Ada"
    assert tree.rows["F-0002"][1] == "Bo"


def test_detail_opens_modal_with_photo_and_grab(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    repo = FakeFaceRepository((_face(),), previews={"F-0001": PREVIEW_PATH})

    _run(Role.ADMIN, repo)
    tree = FakeTreeview.instances[0]
    tree.set_selection(["F-0001"])
    _press(_button_with_text(face_users_gui.USERS_DETAIL_TEXT).command)

    assert len(FakePhotoImage.instances) == 1
    modal = FakeToplevel.instances[-1]
    assert face_users_gui.USERS_DETAIL_TITLE in modal.titles
    assert modal.grab_calls == 1
    assert modal.wait_window_calls == 1


def test_detail_without_photo_shows_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    repo = FakeFaceRepository((_face(),))

    _run(Role.ADMIN, repo)
    tree = FakeTreeview.instances[0]
    tree.set_selection(["F-0001"])
    _press(_button_with_text(face_users_gui.USERS_DETAIL_TEXT).command)

    assert FakePhotoImage.instances == []
    texts = [label.text for label in FakeLabel.instances]
    assert face_users_gui.USERS_MODAL_NO_PHOTO in texts


def test_detail_without_selection_opens_no_modal(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)

    _run(Role.ADMIN, FakeFaceRepository((_face(),)))
    _press(_button_with_text(face_users_gui.USERS_DETAIL_TEXT).command)

    assert len(FakeToplevel.instances) == 1


def test_edit_from_modal_saves_name_and_role(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    repo = FakeFaceRepository((_face(role=Role.OPERATOR),))

    _run(Role.ADMIN, repo)
    tree = FakeTreeview.instances[0]
    tree.set_selection(["F-0001"])
    _press(_button_with_text(face_users_gui.USERS_DETAIL_TEXT).command)
    _press(_button_with_text(face_users_gui.USERS_EDIT_TEXT).command)

    FakeEntry.instances[0].insert(0, "Ada Lovelace")
    FakeStringVar.instances[0].set("viewer")
    _press(_button_with_text(face_users_gui.USERS_SAVE_TEXT).command)

    assert len(repo.updated) == 1
    assert repo.updated[0].name == "Ada Lovelace"
    assert repo.updated[0].role is Role.VIEWER


def test_edit_empty_name_does_not_save(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    repo = FakeFaceRepository((_face(),))

    _run(Role.ADMIN, repo)
    tree = FakeTreeview.instances[0]
    tree.set_selection(["F-0001"])
    _press(_button_with_text(face_users_gui.USERS_DETAIL_TEXT).command)
    _press(_button_with_text(face_users_gui.USERS_EDIT_TEXT).command)
    FakeEntry.instances[0].insert(0, "   ")
    _press(_button_with_text(face_users_gui.USERS_SAVE_TEXT).command)

    assert repo.updated == []


def test_delete_confirmed_removes_face(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    repo = FakeFaceRepository((_face(),))
    FakeMessagebox.answer = True

    _run(Role.ADMIN, repo)
    tree = FakeTreeview.instances[0]
    tree.set_selection(["F-0001"])
    _press(_button_with_text(face_users_gui.USERS_DELETE_TEXT).command)

    assert repo.deleted == ["F-0001"]
    assert len(FakeMessagebox.calls) == 1


def test_delete_cancelled_keeps_face(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    repo = FakeFaceRepository((_face(),))
    FakeMessagebox.answer = False

    _run(Role.ADMIN, repo)
    tree = FakeTreeview.instances[0]
    tree.set_selection(["F-0001"])
    _press(_button_with_text(face_users_gui.USERS_DELETE_TEXT).command)

    assert repo.deleted == []


def test_reenroll_from_modal_runs_runner_with_face_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    from recognizer.cli.apps import face_auth

    seen: list[tuple[str | None, bool]] = []

    def fake_enroll(
        _request: AppRunRequest,
        *,
        reader: Callable[[str], str] | None = None,
        face_id: str | None = None,
    ) -> int:
        seen.append((face_id, reader is not None))
        return 0

    monkeypatch.setattr(face_auth, "run_face_enroll", fake_enroll)
    repo = FakeFaceRepository((_face(),))

    _run(Role.ADMIN, repo)
    tree = FakeTreeview.instances[0]
    tree.set_selection(["F-0001"])
    _press(_button_with_text(face_users_gui.USERS_DETAIL_TEXT).command)
    _press(_button_with_text(face_users_gui.USERS_REENROLL_TEXT).command)

    assert seen == [("F-0001", True)]
    assert FakeToplevel.instances[0].withdraw_calls == 1
    assert FakeToplevel.instances[0].deiconify_calls == 1


def test_close_paths_return_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)

    assert _run(Role.ADMIN, FakeFaceRepository((_face(),))) == 0
    window = FakeToplevel.instances[0]
    window.protocols[menu_gui.EVENT_CLOSE_WINDOW]()
    window.bindings[menu_gui.EVENT_ESCAPE](None)
    _press(_button_with_text(face_users_gui.USERS_BACK_TEXT).command)

    assert window.destroy_calls == 3


def test_table_includes_password_column(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    repo = FakeFaceRepository(
        (
            _face("F-0001", password_hash=hash_password("clave1", iterations=1000)),
            _face("F-0002", "Bo"),
        )
    )

    _run(Role.ADMIN, repo)

    assert "password" in face_users_gui.USERS_COLUMNS
    index = face_users_gui.USERS_COLUMNS.index("password")
    assert face_users_gui.USERS_COLUMN_HEADINGS[index] == "Clave"
    tree = FakeTreeview.instances[0]
    assert tree.rows["F-0001"][index] == face_users_gui.USERS_PASSWORD_YES
    assert tree.rows["F-0002"][index] == face_users_gui.USERS_PASSWORD_NO


def test_edit_sets_new_password(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    repo = FakeFaceRepository((_face(),))

    _run(Role.ADMIN, repo)
    tree = FakeTreeview.instances[0]
    tree.set_selection(["F-0001"])
    _press(_button_with_text(face_users_gui.USERS_DETAIL_TEXT).command)
    _press(_button_with_text(face_users_gui.USERS_EDIT_TEXT).command)

    FakeEntry.instances[1].insert(0, "nueva1")
    FakeEntry.instances[2].insert(0, "nueva1")
    _press(_button_with_text(face_users_gui.USERS_SAVE_TEXT).command)

    assert len(repo.updated) == 1
    assert verify_password("nueva1", repo.updated[0].password_hash)
    assert not verify_password("vieja1", repo.updated[0].password_hash)


def test_edit_mismatched_passwords_aborts_save(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    previous = hash_password("vieja1", iterations=1000)
    repo = FakeFaceRepository((_face(password_hash=previous),))

    _run(Role.ADMIN, repo)
    tree = FakeTreeview.instances[0]
    tree.set_selection(["F-0001"])
    _press(_button_with_text(face_users_gui.USERS_DETAIL_TEXT).command)
    _press(_button_with_text(face_users_gui.USERS_EDIT_TEXT).command)

    FakeEntry.instances[1].insert(0, "nueva1")
    FakeEntry.instances[2].insert(0, "otra12")
    _press(_button_with_text(face_users_gui.USERS_SAVE_TEXT).command)

    # Claves distintas: no se guarda nada (se conserva la anterior).
    assert repo.updated == []


def test_edit_short_password_aborts_save(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    previous = hash_password("vieja1", iterations=1000)
    repo = FakeFaceRepository((_face(password_hash=previous),))

    _run(Role.ADMIN, repo)
    tree = FakeTreeview.instances[0]
    tree.set_selection(["F-0001"])
    _press(_button_with_text(face_users_gui.USERS_DETAIL_TEXT).command)
    _press(_button_with_text(face_users_gui.USERS_EDIT_TEXT).command)

    FakeEntry.instances[1].insert(0, "ab")
    FakeEntry.instances[2].insert(0, "ab")
    _press(_button_with_text(face_users_gui.USERS_SAVE_TEXT).command)

    assert repo.updated == []
