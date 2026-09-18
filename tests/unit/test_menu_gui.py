"""Tests del menu grafico del launcher, sin display real ni hardware."""

from __future__ import annotations

import logging
import sys
import tkinter
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk
from typing import ClassVar, cast

import pytest

from recognizer.cli import menu, menu_gui
from recognizer.cli.menu import LABEL_AVAILABLE, LABEL_COMING_SOON, LABEL_DISABLED
from recognizer.cli.menu_gui import MenuRow, build_menu_rows, run_gui_menu
from recognizer.core.config import AppConfig, AppsConfig
from recognizer.core.domain.app import AppCatalog, AppId, AppRunRequest

REQUEST = AppRunRequest(config_path=Path("config.yaml"))
TEST_LOGGER = logging.getLogger("recognizer.menu.gui.test")
HEAVY_MODULES = ("ultralytics", "torch", "mediapipe", "cv2")


class FakeRoot:
    """Doble de la raiz de tkinter, sin abrir ninguna ventana (modelo FakeRoot)."""

    on_mainloop: ClassVar[Callable[..., None] | None] = None
    instances: ClassVar[list[FakeRoot]] = []

    def __init__(self) -> None:
        self.titles: list[str] = []
        self.protocols: dict[str, Callable[[], None]] = {}
        self.bindings: dict[str, Callable[..., None]] = {}
        self.withdraw_calls = 0
        self.deiconify_calls = 0
        self.destroy_calls = 0
        self.mainloop_calls = 0
        self.instances.append(self)

    def title(self, name: str) -> None:
        self.titles.append(name)

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
        hook = FakeRoot.on_mainloop
        if hook is not None:
            hook(self)


class FakeListbox:
    """Doble de tkinter.Listbox: items y seleccion en memoria."""

    instances: ClassVar[list[FakeListbox]] = []

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.items: list[str] = []
        self.selected: tuple[int, ...] = ()
        self.bindings: dict[str, Callable[..., None]] = {}
        self.instances.append(self)

    def insert(self, _index: object, text: str) -> None:
        self.items.append(text)

    def pack(self, *_args: object, **_kwargs: object) -> None:
        pass

    def selection_set(self, index: int) -> None:
        self.selected = (index,)

    def curselection(self) -> tuple[int, ...]:
        return self.selected

    def bind(self, sequence: str, func: Callable[..., None]) -> None:
        self.bindings[sequence] = func


class FakeFrame:
    """Doble de ttk.Frame sin display."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def pack(self, *_args: object, **_kwargs: object) -> None:
        pass


class FakeButton:
    """Doble de ttk.Button que registra su comando por texto."""

    commands: ClassVar[dict[str, Callable[[], None] | None]] = {}

    def __init__(
        self,
        *_args: object,
        text: str = "",
        command: Callable[[], None] | None = None,
        **_kwargs: object,
    ) -> None:
        self.commands[text] = command

    def pack(self, *_args: object, **_kwargs: object) -> None:
        pass


def _install_tk_fakes(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[type[FakeRoot], type[FakeListbox], type[FakeButton]]:
    """Limpia los fakes de Tk y los instala en tkinter/ttk (sin display)."""
    FakeRoot.on_mainloop = None
    FakeRoot.instances.clear()
    FakeListbox.instances.clear()
    FakeButton.commands.clear()
    monkeypatch.setattr(tkinter, "Listbox", FakeListbox)
    monkeypatch.setattr(ttk, "Frame", FakeFrame)
    monkeypatch.setattr(ttk, "Button", FakeButton)
    return FakeRoot, FakeListbox, FakeButton


def _press_open_button() -> None:
    """Pulsa Abrir en el fake; falla si el boton no existe."""
    open_command = FakeButton.commands[menu_gui.GUI_OPEN_TEXT]
    assert open_command is not None
    open_command()


def _tk_factory() -> Callable[[], tkinter.Tk]:
    """FakeRoot como fabrica de Tk para run_gui_menu."""
    return cast("Callable[[], tkinter.Tk]", FakeRoot)


def test_menu_row_is_frozen() -> None:
    row = MenuRow(number=1, title="t", label="l", app_id=AppId.GESTURES, selectable=True)

    with pytest.raises(AttributeError):
        setattr(row, "title", "x")  # noqa: B010 - ejerce el frozen a proposito


def test_build_menu_rows_reflects_states() -> None:
    rows = build_menu_rows(AppCatalog(), AppsConfig())
    by_id = {row.app_id: row for row in rows}

    assert [row.number for row in rows] == [1, 2, 3, 4, 5, 6, 7]
    assert rows[0].title == "Reconocimiento de gestos"
    assert by_id[AppId.GESTURES].selectable is True
    assert by_id[AppId.GESTURES].label == LABEL_AVAILABLE
    assert by_id[AppId.PEOPLE_COUNTER].selectable is True
    assert by_id[AppId.ANTI_INTRUDER].selectable is False
    assert by_id[AppId.ANTI_INTRUDER].label == LABEL_COMING_SOON

    disabled_config = AppsConfig(enabled={AppId.GESTURES: False})
    disabled = {row.app_id: row for row in build_menu_rows(AppCatalog(), disabled_config)}
    assert disabled[AppId.GESTURES].selectable is False
    assert disabled[AppId.GESTURES].label == LABEL_DISABLED


def test_run_gui_menu_opens_runner_and_returns_to_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_root_cls, fake_listbox_cls, _ = _install_tk_fakes(monkeypatch)
    calls: list[AppRunRequest] = []

    def fake_runner(request: AppRunRequest) -> int:
        calls.append(request)
        return 0

    monkeypatch.setattr(menu, "resolve_runner", lambda _app_id: fake_runner)
    fake_root_cls.on_mainloop = lambda _root: _press_open_button()

    result = run_gui_menu(
        request=REQUEST,
        apps_config=AppsConfig(),
        logger=TEST_LOGGER,
        tk_factory=_tk_factory(),
    )

    root = fake_root_cls.instances[0]
    assert result == 0
    assert calls == [REQUEST]
    assert root.withdraw_calls == 1
    assert root.deiconify_calls == 1
    assert fake_listbox_cls.instances[0].selected == (0,)
    assert len(fake_listbox_cls.instances[0].items) == len(AppCatalog().apps)


def test_run_gui_menu_ignores_non_selectable_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_root_cls, fake_listbox_cls, _ = _install_tk_fakes(monkeypatch)
    calls: list[AppRunRequest] = []

    def fake_runner(request: AppRunRequest) -> int:
        calls.append(request)
        return 0

    def _open_coming_soon(_root: object) -> None:
        fake_listbox_cls.instances[0].selected = (2,)
        _press_open_button()

    monkeypatch.setattr(menu, "resolve_runner", lambda _app_id: fake_runner)
    fake_root_cls.on_mainloop = _open_coming_soon

    result = run_gui_menu(
        request=REQUEST,
        apps_config=AppsConfig(),
        logger=TEST_LOGGER,
        tk_factory=_tk_factory(),
    )

    assert result == 0
    assert calls == []
    assert fake_root_cls.instances[0].withdraw_calls == 0


def test_close_paths_return_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_root_cls, _, fake_button_cls = _install_tk_fakes(monkeypatch)

    result = run_gui_menu(
        request=REQUEST,
        apps_config=AppsConfig(),
        logger=TEST_LOGGER,
        tk_factory=_tk_factory(),
    )

    assert result == 0
    root = fake_root_cls.instances[0]
    assert "WM_DELETE_WINDOW" in root.protocols
    assert "<Escape>" in root.bindings
    assert menu_gui.GUI_EXIT_TEXT in fake_button_cls.commands
    root.protocols["WM_DELETE_WINDOW"]()
    root.bindings["<Escape>"](None)
    close = fake_button_cls.commands[menu_gui.GUI_EXIT_TEXT]
    assert close is not None
    close()
    assert root.destroy_calls == 3


def test_run_launcher_falls_back_to_console_on_tcl_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(menu, "default_config_path", lambda: Path("config.yaml"))
    monkeypatch.setattr(menu, "load_config", lambda _path: AppConfig())

    def _raise_gui(**_kwargs: object) -> int:
        msg = "sin display"
        raise tkinter.TclError(msg)

    monkeypatch.setattr(menu_gui, "run_gui_menu", _raise_gui)
    console_calls: list[dict[str, object]] = []

    def fake_menu(**kwargs: object) -> int:
        console_calls.append(kwargs)
        return 0

    monkeypatch.setattr(menu, "run_menu", fake_menu)

    assert menu.run_launcher() == 0
    assert len(console_calls) == 1


def test_list_only_and_no_gui_do_not_open_gui(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(menu, "default_config_path", lambda: Path("config.yaml"))
    monkeypatch.setattr(menu, "load_config", lambda _path: AppConfig())

    def _fail_gui(**_kwargs: object) -> int:
        msg = "no debe abrir la GUI"
        raise AssertionError(msg)

    monkeypatch.setattr(menu_gui, "run_gui_menu", _fail_gui)
    console_calls: list[dict[str, object]] = []

    def fake_menu(**kwargs: object) -> int:
        console_calls.append(kwargs)
        return 0

    monkeypatch.setattr(menu, "run_menu", fake_menu)

    assert menu.run_launcher(list_only=True) == 0
    assert console_calls == []
    assert menu.run_launcher(use_gui=False) == 0
    assert len(console_calls) == 1


def test_opening_menu_does_not_import_heavy_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(menu, "default_config_path", lambda: Path("config.yaml"))
    monkeypatch.setattr(menu, "load_config", lambda _path: AppConfig())

    before = set(sys.modules)

    assert menu.run_launcher(list_only=True) == 0

    added = set(sys.modules) - before
    for heavy in HEAVY_MODULES:
        assert heavy not in added


def test_app_main_no_gui_and_list_apps_skip_gui(monkeypatch: pytest.MonkeyPatch) -> None:
    from recognizer.cli import app as app_module

    calls: list[dict[str, object]] = []

    def fake_launcher(**kwargs: object) -> int:
        calls.append(kwargs)
        return 0

    monkeypatch.setattr(menu, "run_launcher", fake_launcher)

    assert app_module.main(["--no-gui"]) == 0
    assert app_module.main(["--list-apps"]) == 0
    assert calls[0] == {"use_gui": False}
    assert calls[1] == {"list_only": True}


def test_spec_includes_menu_gui_hiddenimport() -> None:
    spec = Path(__file__).resolve().parents[2] / "packaging" / "recognizer.spec"

    assert "recognizer.cli.menu_gui" in spec.read_text(encoding="utf-8")
