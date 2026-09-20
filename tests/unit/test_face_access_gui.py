"""Tests del panel de accesos faciales (tkinter falso), sin display ni hardware."""

from __future__ import annotations

import logging
import tkinter
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar, cast

import pytest

from recognizer.adapters.file_access_log_repository import FileAccessLogRepository
from recognizer.cli import face_access_gui, menu_gui
from recognizer.cli.face_access_gui import run_access_panel
from recognizer.core.domain.access import AccessEvent, AccessMethod
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.domain.identity import Identity, Role
from recognizer.core.ports.access_log import AccessLogRepository

REQUEST = AppRunRequest(config_path=Path("config.yaml"))
TEST_LOGGER = logging.getLogger("recognizer.menu.face.access.test")
TS_OLD = "2026-09-19T10:00:00+00:00"
TS_NEW = "2026-09-19T12:00:00+00:00"
PNG_BYTES = b"\x89PNG\r\n\x1a\nfake"


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

    def grab_set(self) -> None:
        self.grab_calls += 1

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
        self.row_tags: dict[str, tuple[str, ...]] = {}
        self.tag_styles: dict[str, dict[str, object]] = {}
        self._selection: list[str] = []
        FakeTreeview.instances.append(self)

    def heading(self, *_args: object, **_kwargs: object) -> None:
        pass

    def column(self, *_args: object, **_kwargs: object) -> None:
        pass

    def tag_configure(self, tag: str, **kwargs: object) -> None:
        self.tag_styles[tag] = dict(kwargs)

    def insert(
        self,
        _parent: str,
        _index: str,
        *,
        iid: str,
        values: object,
        tags: tuple[str, ...] = (),
    ) -> None:
        self.rows[iid] = tuple(values)  # type: ignore[arg-type]
        self.row_tags[iid] = tuple(tags)

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


class FakeAccessRepository:
    """Doble del puerto AccessLogRepository que registra que metodo se uso."""

    def __init__(self, events: tuple[AccessEvent, ...] = ()) -> None:
        self.events = events
        self.list_all_calls = 0
        self.find_calls: list[str] = []

    def append(self, *, event: AccessEvent, image: bytes | None) -> AccessEvent:
        raise NotImplementedError

    def list_all(self) -> tuple[AccessEvent, ...]:
        self.list_all_calls += 1
        return self.events

    def find_by_face(self, face_id: str) -> tuple[AccessEvent, ...]:
        self.find_calls.append(face_id)
        return tuple(event for event in self.events if event.face_id == face_id)

    def image_path(self, _event: AccessEvent) -> Path | None:
        return None


def _event(
    face_id: str,
    name: str,
    timestamp: str,
    *,
    method: AccessMethod = AccessMethod.FACE,
    success: bool = True,
) -> AccessEvent:
    return AccessEvent(
        face_id=face_id,
        name=name,
        role=Role.OPERATOR,
        timestamp=timestamp,
        image="",
        method=method,
        success=success,
    )


def _identity(face_id: str, role: Role) -> Identity:
    return Identity(face_id=face_id, name="Ada", role=role, authenticated_at="hoy")


def _install_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeToplevel.instances.clear()
    FakeFrame.instances.clear()
    FakeLabel.instances.clear()
    FakeButton.instances.clear()
    FakePhotoImage.instances.clear()
    FakeTreeview.instances.clear()
    FakeScrollbar.instances.clear()
    monkeypatch.setattr(tkinter, "Frame", FakeFrame)
    monkeypatch.setattr(tkinter, "Label", FakeLabel)
    monkeypatch.setattr(tkinter, "Button", FakeButton)
    monkeypatch.setattr(tkinter, "PhotoImage", FakePhotoImage)
    monkeypatch.setattr(tkinter, "Toplevel", FakeToplevel)
    monkeypatch.setattr(tkinter, "ttk", FakeTtk, raising=False)
    monkeypatch.setattr(tkinter, "messagebox", object(), raising=False)


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
    identity: Identity,
    repository: AccessLogRepository,
    *,
    show_photos: bool = True,
) -> int:
    return run_access_panel(
        REQUEST,
        tk_factory=_tk_factory(),
        repository=repository,
        identity=identity,
        show_photos=show_photos,
        logger=TEST_LOGGER,
    )


def _has_button(text: str) -> bool:
    return any(button.text == text for button in FakeButton.instances)


def test_non_admin_filters_by_face_and_hides_photos(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    repo = FakeAccessRepository((_event("F-0001", "Ada", TS_OLD), _event("F-0002", "Bo", TS_NEW)))

    result = _run(_identity("F-0002", Role.OPERATOR), repo, show_photos=True)

    assert result == 0
    assert repo.list_all_calls == 0
    assert repo.find_calls == ["F-0002"]
    tree = FakeTreeview.instances[0]
    assert tuple(tree.rows) == ("0",)
    assert tree.rows["0"][2] == "F-0002"
    assert not _has_button(face_access_gui.ACCESS_VIEW_TEXT)
    assert FakePhotoImage.instances == []


def test_admin_sees_all_events(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    repo = FakeAccessRepository((_event("F-0001", "Ada", TS_OLD), _event("F-0002", "Bo", TS_NEW)))

    result = _run(_identity("F-0001", Role.ADMIN), repo)

    assert result == 0
    assert repo.list_all_calls == 1
    assert repo.find_calls == []
    tree = FakeTreeview.instances[0]
    assert tuple(tree.rows) == ("0", "1")
    assert _has_button(face_access_gui.ACCESS_VIEW_TEXT)


def test_admin_view_image_opens_modal_with_photo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fakes(monkeypatch)
    repo = FileAccessLogRepository(tmp_path / "access")
    repo.append(event=_event("F-0001", "Ada", TS_NEW), image=PNG_BYTES)

    _run(_identity("F-0001", Role.ADMIN), repo)
    tree = FakeTreeview.instances[0]
    tree.set_selection(["0"])
    _press(_button_with_text(face_access_gui.ACCESS_VIEW_TEXT).command)

    assert len(FakePhotoImage.instances) == 1
    modal = FakeToplevel.instances[-1]
    assert face_access_gui.ACCESS_MODAL_TITLE in modal.titles
    assert modal.grab_calls == 1


def test_view_image_without_selection_opens_no_modal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fakes(monkeypatch)
    repo = FileAccessLogRepository(tmp_path / "access")
    repo.append(event=_event("F-0001", "Ada", TS_NEW), image=PNG_BYTES)

    _run(_identity("F-0001", Role.ADMIN), repo)
    _press(_button_with_text(face_access_gui.ACCESS_VIEW_TEXT).command)

    assert FakePhotoImage.instances == []


def test_non_admin_never_shows_photo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    repo = FileAccessLogRepository(tmp_path / "access")
    repo.append(event=_event("F-0001", "Ada", TS_NEW), image=PNG_BYTES)

    _run(_identity("F-0001", Role.OPERATOR), repo, show_photos=True)

    assert not _has_button(face_access_gui.ACCESS_VIEW_TEXT)
    assert FakePhotoImage.instances == []


def test_non_admin_header_uses_my_subtitle(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)

    _run(
        _identity("F-0002", Role.OPERATOR),
        FakeAccessRepository((_event("F-0002", "Bo", TS_NEW),)),
    )

    texts = [label.text for label in FakeLabel.instances]
    assert face_access_gui.ACCESS_MY_HEADER_SUBTITLE in texts
    assert face_access_gui.ACCESS_HEADER_SUBTITLE not in texts


def test_missing_repository_returns_one(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    from recognizer.cli import face_adapters

    monkeypatch.setattr(face_adapters, "default_access_repository", lambda *_a, **_k: None)

    result = run_access_panel(
        REQUEST,
        tk_factory=_tk_factory(),
        repository=None,
        identity=_identity("F-0001", Role.ADMIN),
        show_photos=True,
        logger=TEST_LOGGER,
    )

    assert result == 1
    assert FakeToplevel.instances == []


def test_rows_show_method_result_and_color_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    repo = FakeAccessRepository(
        (
            _event("F-0001", "Ada", TS_OLD),
            _event("F-0002", "Bo", TS_NEW, method=AccessMethod.PASSWORD, success=False),
        )
    )

    _run(_identity("F-0001", Role.ADMIN), repo)

    tree = FakeTreeview.instances[0]
    method_index = face_access_gui.ACCESS_COLUMNS.index("method")
    result_index = face_access_gui.ACCESS_COLUMNS.index("result")
    assert tree.rows["0"][method_index] == AccessMethod.FACE.value
    assert tree.rows["0"][result_index] == face_access_gui.ACCESS_RESULT_OK_TEXT
    assert tree.rows["1"][method_index] == AccessMethod.PASSWORD.value
    assert tree.rows["1"][result_index] == face_access_gui.ACCESS_RESULT_FAIL_TEXT
    assert tree.row_tags["0"] == (face_access_gui.ACCESS_TAG_OK,)
    assert tree.row_tags["1"] == (face_access_gui.ACCESS_TAG_FAIL,)
    assert tree.tag_styles[face_access_gui.ACCESS_TAG_OK]["foreground"] == (
        menu_gui.DEFAULT_THEME.success
    )
    assert tree.tag_styles[face_access_gui.ACCESS_TAG_FAIL]["foreground"] == (
        menu_gui.DEFAULT_THEME.danger
    )


def _modal_texts() -> list[str]:
    return [label.text for label in FakeLabel.instances]


def test_password_failure_modal_shows_red_status_and_no_photo_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fakes(monkeypatch)
    repo = FakeAccessRepository(
        (_event("F-0002", "Bo", TS_NEW, method=AccessMethod.PASSWORD, success=False),)
    )

    _run(_identity("F-0001", Role.ADMIN), repo)
    tree = FakeTreeview.instances[0]
    tree.set_selection(["0"])
    _press(_button_with_text(face_access_gui.ACCESS_VIEW_TEXT).command)

    texts = _modal_texts()
    assert face_access_gui.ACCESS_STATUS_PASSWORD_FAIL in texts
    assert face_access_gui.ACCESS_MODAL_NO_PHOTO_PASSWORD in texts
    assert face_access_gui.ACCESS_STATUS_PASSWORD_OK not in texts


def test_password_success_modal_explains_missing_photo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fakes(monkeypatch)
    repo = FakeAccessRepository(
        (_event("F-0001", "Ada", TS_NEW, method=AccessMethod.PASSWORD, success=True),)
    )

    _run(_identity("F-0001", Role.ADMIN), repo)
    tree = FakeTreeview.instances[0]
    tree.set_selection(["0"])
    _press(_button_with_text(face_access_gui.ACCESS_VIEW_TEXT).command)

    texts = _modal_texts()
    assert face_access_gui.ACCESS_STATUS_PASSWORD_OK in texts
    assert face_access_gui.ACCESS_MODAL_NO_PHOTO_PASSWORD in texts


def test_face_success_modal_shows_face_status(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    repo = FakeAccessRepository((_event("F-0001", "Ada", TS_NEW),))

    _run(_identity("F-0001", Role.ADMIN), repo)
    tree = FakeTreeview.instances[0]
    tree.set_selection(["0"])
    _press(_button_with_text(face_access_gui.ACCESS_VIEW_TEXT).command)

    assert face_access_gui.ACCESS_STATUS_FACE_OK in _modal_texts()


def test_close_paths_return_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)

    assert _run(_identity("F-0001", Role.ADMIN), FakeAccessRepository(())) == 0
    window = FakeToplevel.instances[0]
    window.protocols[menu_gui.EVENT_CLOSE_WINDOW]()
    window.bindings[menu_gui.EVENT_ESCAPE](None)
    _press(_button_with_text(face_access_gui.ACCESS_BACK_TEXT).command)

    assert window.destroy_calls == 3
