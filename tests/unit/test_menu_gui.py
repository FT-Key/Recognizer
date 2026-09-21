"""Tests del menu grafico del launcher, sin display real ni hardware.

El modulo `menu_gui` resuelve los widgets como atributos de `tkinter` en tiempo
de llamada, asi que basta con parchear `tkinter.Frame/Label/Button/PhotoImage/
Canvas/Scrollbar` e inyectar `FakeRoot` via `tk_factory`. Los assets se anulan
para que el branding no toque el sistema de archivos ni registre fuentes.
"""

from __future__ import annotations

import logging
import sys
import tkinter
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar, cast

import pytest

from recognizer.cli import menu, menu_gui
from recognizer.cli.menu import LABEL_AVAILABLE, LABEL_COMING_SOON, LABEL_DISABLED
from recognizer.cli.menu_gui import (
    DEFAULT_THEME,
    WRAPLENGTH_MIN,
    MenuRow,
    _apply_branding,
    _apply_window_icon,
    _badge_background,
    _button_wraplength,
    _center_window,
    badge_foreground,
    build_menu_rows,
    compute_window_geometry,
    run_gui_menu,
)
from recognizer.core.config import AppConfig, AppsConfig
from recognizer.core.domain.app import (
    AppAvailability,
    AppCatalog,
    AppId,
    AppPreparation,
    AppRunRequest,
)

REQUEST = AppRunRequest(config_path=Path("config.yaml"))
TEST_LOGGER = logging.getLogger("recognizer.menu.gui.test")
HEAVY_MODULES = ("ultralytics", "torch", "mediapipe", "cv2")
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080


class FakeRoot:
    """Doble de la raiz de tkinter, sin abrir ninguna ventana (modelo FakeRoot)."""

    on_mainloop: ClassVar[Callable[..., None] | None] = None
    instances: ClassVar[list[FakeRoot]] = []
    screen_width: ClassVar[int] = SCREEN_WIDTH
    screen_height: ClassVar[int] = SCREEN_HEIGHT
    iconbitmap_error: ClassVar[type[Exception] | None] = None

    def __init__(self) -> None:
        self.titles: list[str] = []
        self.protocols: dict[str, Callable[[], None]] = {}
        self.bindings: dict[str, Callable[..., None]] = {}
        self.geometry_calls: list[str] = []
        self.withdraw_calls = 0
        self.deiconify_calls = 0
        self.destroy_calls = 0
        self.mainloop_calls = 0
        self.instances.append(self)

    def title(self, name: str) -> None:
        self.titles.append(name)

    def configure(self, *_args: object, **_kwargs: object) -> None:
        pass

    def geometry(self, value: str) -> None:
        self.geometry_calls.append(value)

    def minsize(self, *_args: object) -> None:
        pass

    def resizable(self, *_args: object) -> None:
        pass

    def winfo_screenwidth(self) -> int:
        return type(self).screen_width

    def winfo_screenheight(self) -> int:
        return type(self).screen_height

    def iconbitmap(self, *_args: object, **_kwargs: object) -> None:
        error = type(self).iconbitmap_error
        if error is not None:
            raise error("icono no disponible")

    def iconphoto(self, *_args: object, **_kwargs: object) -> None:
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
        hook = FakeRoot.on_mainloop
        if hook is not None:
            hook(self)


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
        pass

    def focus_set(self) -> None:
        pass


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
        self.fg = kwargs.get("fg")
        self.bg = kwargs.get("bg")
        FakeLabel.instances.append(self)


class FakeButton(_WidgetBase):
    """Doble de tkinter.Button que registra texto, comando y estado."""

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
        self.state = str(kwargs.get("state", menu_gui.STATE_NORMAL))
        self.wraplength = kwargs.get("wraplength")
        FakeButton.instances.append(self)


class FakePhotoImage(_WidgetBase):
    """Doble de tkinter.PhotoImage (no lee ningun archivo)."""

    instances: ClassVar[list[FakePhotoImage]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        FakePhotoImage.instances.append(self)


class FakeCanvas(_WidgetBase):
    """Doble de tkinter.Canvas: ventana embebida y scroll no-op."""

    instances: ClassVar[list[FakeCanvas]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.windows: list[object] = []
        self.itemconfigure_calls: list[tuple[object, dict[str, object]]] = []
        self.scroll_calls: list[tuple[int, str]] = []
        FakeCanvas.instances.append(self)

    def create_window(self, *_args: object, window: object = None, **_kwargs: object) -> int:
        self.windows.append(window)
        return len(self.windows)

    def bbox(self, *_args: object) -> tuple[int, int, int, int]:
        return (0, 0, 0, 0)

    def itemconfigure(self, item: object, **kwargs: object) -> None:
        self.itemconfigure_calls.append((item, kwargs))

    def yview(self, *_args: object) -> None:
        pass

    def yview_scroll(self, number: int, what: str) -> None:
        self.scroll_calls.append((number, what))


class FakeScrollbar(_WidgetBase):
    """Doble de tkinter.Scrollbar sin display."""

    instances: ClassVar[list[FakeScrollbar]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        FakeScrollbar.instances.append(self)

    def set(self, *_args: object) -> None:
        pass


class FakeTreeview(_WidgetBase):
    """Doble de tkinter.ttk.Treeview (filas en memoria)."""

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

    def yview(self, *_args: object) -> None:
        pass


class FakeTtkScrollbar(_WidgetBase):
    """Doble de tkinter.ttk.Scrollbar."""

    instances: ClassVar[list[FakeTtkScrollbar]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        FakeTtkScrollbar.instances.append(self)

    def set(self, *_args: object) -> None:
        pass


class FakeTtk:
    """Doble del submodulo tkinter.ttk."""

    Treeview = FakeTreeview
    Scrollbar = FakeTtkScrollbar


class FakeMessagebox:
    """Doble de tkinter.messagebox con respuesta programable."""

    answer: ClassVar[bool] = True

    @classmethod
    def askyesno(cls, _title: str, _message: str, **_kwargs: object) -> bool:
        return cls.answer


def _install_tk_fakes(monkeypatch: pytest.MonkeyPatch) -> type[FakeRoot]:
    """Limpia los fakes de Tk y los instala en tkinter (sin display)."""
    FakeRoot.on_mainloop = None
    FakeRoot.instances.clear()
    FakeRoot.screen_width = SCREEN_WIDTH
    FakeRoot.screen_height = SCREEN_HEIGHT
    FakeRoot.iconbitmap_error = None
    FakeFrame.instances.clear()
    FakeLabel.instances.clear()
    FakeButton.instances.clear()
    FakePhotoImage.instances.clear()
    FakeCanvas.instances.clear()
    FakeScrollbar.instances.clear()
    FakeTreeview.instances.clear()
    FakeTtkScrollbar.instances.clear()
    FakeMessagebox.answer = True
    monkeypatch.setattr(tkinter, "Frame", FakeFrame)
    monkeypatch.setattr(tkinter, "Label", FakeLabel)
    monkeypatch.setattr(tkinter, "Button", FakeButton)
    monkeypatch.setattr(tkinter, "PhotoImage", FakePhotoImage)
    monkeypatch.setattr(tkinter, "Canvas", FakeCanvas)
    monkeypatch.setattr(tkinter, "Scrollbar", FakeScrollbar)
    monkeypatch.setattr(tkinter, "ttk", FakeTtk, raising=False)
    monkeypatch.setattr(tkinter, "messagebox", FakeMessagebox, raising=False)
    monkeypatch.setattr(menu_gui, "display_font_paths", lambda: ())
    monkeypatch.setattr(menu_gui, "desktop_icon_path", lambda: None)
    monkeypatch.setattr(menu_gui, "desktop_logo_path", lambda: None)
    return FakeRoot


def _button_with_text(text: str) -> FakeButton:
    for button in FakeButton.instances:
        if button.text == text:
            return button
    msg = f"no existe el boton {text!r}"
    raise AssertionError(msg)


def _app_button(number: int) -> FakeButton:
    prefix = f"{number}. "
    for button in FakeButton.instances:
        if button.text.startswith(prefix):
            return button
    msg = f"no existe el boton de la app {number}"
    raise AssertionError(msg)


def _press(command: Callable[[], None] | None) -> None:
    assert command is not None
    command()


def _press_open_button() -> None:
    """Pulsa Abrir en el fake; falla si el boton no existe."""
    _press(_button_with_text(menu_gui.GUI_OPEN_TEXT).command)


def _tk_factory() -> Callable[[], tkinter.Tk]:
    """FakeRoot como fabrica de Tk para run_gui_menu."""
    return cast("Callable[[], tkinter.Tk]", FakeRoot)


def test_menu_row_is_frozen() -> None:
    row = MenuRow(number=1, title="t", label="l", app_id=AppId.GESTURES, selectable=True)

    with pytest.raises(AttributeError):
        setattr(row, "title", "x")  # noqa: B010 - ejerce el frozen a proposito


def test_build_menu_rows_reflects_states_and_descriptions() -> None:
    rows = build_menu_rows(AppCatalog(), AppsConfig())
    by_id = {row.app_id: row for row in rows}

    assert [row.number for row in rows] == list(range(1, len(rows) + 1))
    assert rows[0].title == "Reconocimiento de gestos"
    assert rows[0].description == "Controla el equipo con gestos de mano (MediaPipe)."
    assert by_id[AppId.GESTURES].selectable is True
    assert by_id[AppId.GESTURES].label == LABEL_AVAILABLE
    assert by_id[AppId.GESTURES].availability is AppAvailability.AVAILABLE
    assert by_id[AppId.PEOPLE_COUNTER].selectable is True
    assert by_id[AppId.ANTI_INTRUDER].selectable is True
    assert by_id[AppId.ANTI_INTRUDER].label == LABEL_AVAILABLE
    assert by_id[AppId.ANTI_INTRUDER].availability is AppAvailability.AVAILABLE
    assert by_id[AppId.POSTURE].selectable is True
    assert by_id[AppId.POSTURE].label == LABEL_AVAILABLE
    assert by_id[AppId.POSTURE].availability is AppAvailability.AVAILABLE
    assert by_id[AppId.PPE_DETECTOR].selectable is False
    assert LABEL_COMING_SOON in by_id[AppId.PPE_DETECTOR].label
    assert by_id[AppId.PPE_DETECTOR].availability is AppAvailability.COMING_SOON

    disabled_config = AppsConfig(enabled={AppId.GESTURES: False})
    disabled = {row.app_id: row for row in build_menu_rows(AppCatalog(), disabled_config)}
    assert disabled[AppId.GESTURES].selectable is False
    assert disabled[AppId.GESTURES].label == LABEL_DISABLED
    assert disabled[AppId.GESTURES].availability is AppAvailability.DISABLED


def test_badge_background_maps_availability() -> None:
    assert _badge_background(AppAvailability.AVAILABLE, DEFAULT_THEME) == DEFAULT_THEME.primary
    assert _badge_background(AppAvailability.DISABLED, DEFAULT_THEME) == DEFAULT_THEME.neutral
    assert _badge_background(AppAvailability.COMING_SOON, DEFAULT_THEME) == DEFAULT_THEME.warning
    assert _badge_background(cast(AppAvailability, "desconocido"), DEFAULT_THEME) == (
        DEFAULT_THEME.neutral
    )


def test_badge_foreground_maps_contrast_color() -> None:
    assert badge_foreground(AppAvailability.AVAILABLE, DEFAULT_THEME) == (
        DEFAULT_THEME.primary_contrast
    )
    assert badge_foreground(AppAvailability.DISABLED, DEFAULT_THEME) == DEFAULT_THEME.text
    assert badge_foreground(AppAvailability.COMING_SOON, DEFAULT_THEME) == DEFAULT_THEME.text
    assert badge_foreground(cast(AppAvailability, "desconocido"), DEFAULT_THEME) == (
        DEFAULT_THEME.text
    )


def test_compute_window_geometry_centers_and_uses_top_third() -> None:
    width, height, x, y = compute_window_geometry(7, SCREEN_WIDTH, SCREEN_HEIGHT)

    assert width == menu_gui.WINDOW_WIDTH
    assert height >= menu_gui.WINDOW_MIN_HEIGHT
    assert x == (SCREEN_WIDTH - menu_gui.WINDOW_WIDTH) // 2
    assert y == max(0, (SCREEN_HEIGHT - height) // menu_gui.WINDOW_TOP_DIVISOR)


def test_compute_window_geometry_fits_every_row_on_tall_screen() -> None:
    tall_screen = 4000
    _, height, _, _ = compute_window_geometry(7, SCREEN_WIDTH, tall_screen)

    assert height == max(menu_gui._window_height(7), menu_gui.WINDOW_MIN_HEIGHT)
    assert height > menu_gui._window_height(1)


def test_compute_window_geometry_clamps_to_screen_ratio() -> None:
    screen_height = 720
    _, height, _, _ = compute_window_geometry(50, 1280, screen_height)
    expected = max(
        menu_gui.WINDOW_MIN_HEIGHT,
        round(screen_height * menu_gui.WINDOW_SCREEN_HEIGHT_RATIO),
    )

    assert height == expected


def test_compute_window_geometry_respects_minimum_and_clamps_x() -> None:
    _, height, x, _ = compute_window_geometry(0, 400, SCREEN_HEIGHT)

    assert height == menu_gui.WINDOW_MIN_HEIGHT
    assert x == 0


def test_compute_window_geometry_clamps_width_to_narrow_screen() -> None:
    narrow_width = menu_gui.WINDOW_WIDTH - 160
    width, _, x, _ = compute_window_geometry(7, narrow_width, SCREEN_HEIGHT)

    assert width == narrow_width
    assert width < menu_gui.WINDOW_WIDTH
    assert x == 0


def test_button_wraplength_shrinks_with_width_and_respects_floor() -> None:
    wide = _button_wraplength(menu_gui.WINDOW_WIDTH)
    narrower = _button_wraplength(menu_gui.WINDOW_MIN_WIDTH)

    assert wide > narrower >= WRAPLENGTH_MIN
    assert _button_wraplength(0) == WRAPLENGTH_MIN


def test_center_window_returns_real_width_and_clamps_on_narrow_screen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_root_cls = _install_tk_fakes(monkeypatch)

    assert (
        _center_window(cast("tkinter.Tk", fake_root_cls()), row_count=7, logger=TEST_LOGGER)
        == menu_gui.WINDOW_WIDTH
    )

    fake_root_cls.screen_width = menu_gui.WINDOW_WIDTH - 120
    narrow = _center_window(cast("tkinter.Tk", fake_root_cls()), row_count=7, logger=TEST_LOGGER)
    assert narrow == menu_gui.WINDOW_WIDTH - 120


def test_run_gui_menu_badges_use_contrast_foreground(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_tk_fakes(monkeypatch)
    monkeypatch.setattr(menu, "resolve_runner", lambda _app_id: None)
    disabled_config = AppsConfig(enabled={AppId.GESTURES: False})

    assert (
        run_gui_menu(
            request=REQUEST,
            apps_config=disabled_config,
            logger=TEST_LOGGER,
            tk_factory=_tk_factory(),
        )
        == 0
    )

    training_label = f"{LABEL_COMING_SOON} - requiere {AppPreparation.TRAINING.value}"
    badges = {label.text: label for label in FakeLabel.instances}
    assert badges[LABEL_AVAILABLE].fg == DEFAULT_THEME.primary_contrast
    assert badges[training_label].fg == DEFAULT_THEME.text
    # FACE_AUTH (enrolamiento) ya está implementada: usa badge disponible.
    assert f"{LABEL_COMING_SOON} - requiere {AppPreparation.ENROLLMENT.value}" not in badges
    assert badges[LABEL_DISABLED].fg == DEFAULT_THEME.text


def test_run_gui_menu_uses_clamped_width_for_wraplength_on_narrow_screen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_root_cls = _install_tk_fakes(monkeypatch)
    fake_root_cls.screen_width = 600
    monkeypatch.setattr(menu, "resolve_runner", lambda _app_id: None)

    assert (
        run_gui_menu(
            request=REQUEST,
            apps_config=AppsConfig(),
            logger=TEST_LOGGER,
            tk_factory=_tk_factory(),
        )
        == 0
    )

    expected = _button_wraplength(600)
    assert expected < _button_wraplength(menu_gui.WINDOW_WIDTH)
    app_buttons = [button for button in FakeButton.instances if button.text[:1].isdigit()]
    assert app_buttons
    assert all(button.wraplength == expected for button in app_buttons)


def test_apply_window_icon_returns_photo_for_retention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_root_cls = _install_tk_fakes(monkeypatch)
    monkeypatch.setattr(menu_gui, "desktop_icon_path", lambda: Path("minilogo.ico"))
    monkeypatch.setattr(menu_gui, "desktop_logo_path", lambda: Path("minilogo-128.png"))
    fake_root_cls.iconbitmap_error = tkinter.TclError

    photo = _apply_window_icon(cast("tkinter.Tk", fake_root_cls()), logger=TEST_LOGGER)

    assert photo is not None
    assert any(cast(object, photo) is instance for instance in FakePhotoImage.instances)


def test_apply_branding_retains_icon_and_logo(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_root_cls = _install_tk_fakes(monkeypatch)
    monkeypatch.setattr(menu_gui, "desktop_icon_path", lambda: Path("minilogo.ico"))
    monkeypatch.setattr(menu_gui, "desktop_logo_path", lambda: Path("minilogo-128.png"))
    fake_root_cls.iconbitmap_error = tkinter.TclError

    branding = _apply_branding(cast("tkinter.Tk", fake_root_cls()), logger=TEST_LOGGER)

    assert branding.icon is not None
    assert branding.logo is not None


def test_run_gui_menu_opens_runner_and_returns_to_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_root_cls = _install_tk_fakes(monkeypatch)
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
    assert _app_button(1).state == menu_gui.STATE_NORMAL
    assert root.geometry_calls


def test_run_gui_menu_ignores_non_selectable_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_root_cls = _install_tk_fakes(monkeypatch)
    calls: list[AppRunRequest] = []

    def fake_runner(request: AppRunRequest) -> int:
        calls.append(request)
        return 0

    monkeypatch.setattr(menu, "resolve_runner", lambda _app_id: fake_runner)
    # Posicion 11 = FALL_DETECTOR (proximamente): fila no seleccionable.
    fake_root_cls.on_mainloop = lambda _root: _press(_app_button(11).command)

    result = run_gui_menu(
        request=REQUEST,
        apps_config=AppsConfig(),
        logger=TEST_LOGGER,
        tk_factory=_tk_factory(),
    )

    assert result == 0
    assert calls == []
    assert fake_root_cls.instances[0].withdraw_calls == 0
    assert _app_button(11).state == menu_gui.STATE_DISABLED


def test_close_paths_return_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_root_cls = _install_tk_fakes(monkeypatch)

    result = run_gui_menu(
        request=REQUEST,
        apps_config=AppsConfig(),
        logger=TEST_LOGGER,
        tk_factory=_tk_factory(),
    )

    assert result == 0
    root = fake_root_cls.instances[0]
    assert menu_gui.EVENT_CLOSE_WINDOW in root.protocols
    assert menu_gui.EVENT_ESCAPE in root.bindings
    exit_command = _button_with_text(menu_gui.GUI_EXIT_TEXT).command
    root.protocols[menu_gui.EVENT_CLOSE_WINDOW]()
    root.bindings[menu_gui.EVENT_ESCAPE](None)
    _press(exit_command)
    assert root.destroy_calls == 3


def test_mousewheel_over_any_widget_scrolls_the_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_root_cls = _install_tk_fakes(monkeypatch)
    monkeypatch.setattr(menu, "resolve_runner", lambda _app_id: None)

    assert (
        run_gui_menu(
            request=REQUEST,
            apps_config=AppsConfig(),
            logger=TEST_LOGGER,
            tk_factory=_tk_factory(),
        )
        == 0
    )

    root = fake_root_cls.instances[0]
    canvas = FakeCanvas.instances[0]
    handler = root.bindings[menu_gui.EVENT_MOUSEWHEEL]

    handler(SimpleNamespace(delta=menu_gui.WHEEL_DELTA))
    handler(SimpleNamespace(delta=-menu_gui.WHEEL_DELTA))
    handler(SimpleNamespace(delta=0))

    assert canvas.scroll_calls == [(-1, menu_gui.SCROLL_UNITS), (1, menu_gui.SCROLL_UNITS)]


def test_keyboard_interrupt_in_mainloop_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_root_cls = _install_tk_fakes(monkeypatch)

    def _interrupt(_root: FakeRoot) -> None:
        raise KeyboardInterrupt

    fake_root_cls.on_mainloop = _interrupt

    assert (
        run_gui_menu(
            request=REQUEST,
            apps_config=AppsConfig(),
            logger=TEST_LOGGER,
            tk_factory=_tk_factory(),
        )
        == 0
    )


def test_opening_gui_menu_does_not_import_heavy_deps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_tk_fakes(monkeypatch)
    monkeypatch.setattr(menu, "resolve_runner", lambda _app_id: None)
    before = set(sys.modules)

    assert (
        run_gui_menu(
            request=REQUEST,
            apps_config=AppsConfig(),
            logger=TEST_LOGGER,
            tk_factory=_tk_factory(),
        )
        == 0
    )

    added = set(sys.modules) - before
    for heavy in HEAVY_MODULES:
        assert heavy not in added


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


def test_list_only_does_not_import_heavy_deps(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_spec_bundles_assets_and_icon() -> None:
    spec = Path(__file__).resolve().parents[2] / "packaging" / "recognizer.spec"
    text = spec.read_text(encoding="utf-8")

    assert "assets" in text
    assert "minilogo.ico" in text
