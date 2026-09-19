"""Tests del dialogo de login con clave (tkinter falso), sin display ni hardware."""

from __future__ import annotations

import logging
import tkinter
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar, cast

import pytest

from recognizer.cli import face_password_gui, menu_gui
from recognizer.cli.face_password_gui import run_password_login
from recognizer.core.constants import FACE_LOGIN_PASSWORD_PROMPT, FACE_LOGIN_USER_PROMPT
from recognizer.core.domain.app import AppRunRequest

REQUEST = AppRunRequest(config_path=Path("config.yaml"))
TEST_LOGGER = logging.getLogger("recognizer.menu.face.password.test")


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


class FakeRunner:
    """Doble del runner de login por clave: lee usuario y clave del reader."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def __call__(self, request: AppRunRequest, *, reader: Callable[[str], str]) -> int:
        del request
        self.calls.append((reader(FACE_LOGIN_USER_PROMPT), reader(FACE_LOGIN_PASSWORD_PROMPT)))
        return 0


def _install_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeToplevel.instances.clear()
    FakeFrame.instances.clear()
    FakeLabel.instances.clear()
    FakeButton.instances.clear()
    FakeEntry.instances.clear()
    monkeypatch.setattr(tkinter, "Frame", FakeFrame)
    monkeypatch.setattr(tkinter, "Label", FakeLabel)
    monkeypatch.setattr(tkinter, "Button", FakeButton)
    monkeypatch.setattr(tkinter, "Entry", FakeEntry)


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


def _run(runner: face_password_gui.PasswordLoginRunner | None = None) -> int:
    return run_password_login(
        REQUEST,
        tk_factory=_tk_factory(),
        password_runner=runner,
        logger=TEST_LOGGER,
    )


def test_login_calls_runner_with_user_and_password(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    runner = FakeRunner()

    _run(cast("face_password_gui.PasswordLoginRunner", runner))
    FakeEntry.instances[0].set_text("Ada")
    FakeEntry.instances[1].set_text("clave1")
    _press(_button_with_text(face_password_gui.PASSWORD_LOGIN_TEXT).command)

    assert runner.calls == [("Ada", "clave1")]
    window = FakeToplevel.instances[0]
    assert window.withdraw_calls == 1
    assert window.deiconify_calls == 1
    assert window.destroy_calls == 1


def test_empty_credentials_do_not_call_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    runner = FakeRunner()

    _run(cast("face_password_gui.PasswordLoginRunner", runner))
    _press(_button_with_text(face_password_gui.PASSWORD_LOGIN_TEXT).command)

    assert runner.calls == []
    assert FakeToplevel.instances[0].destroy_calls == 0


def test_missing_password_does_not_call_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    runner = FakeRunner()

    _run(cast("face_password_gui.PasswordLoginRunner", runner))
    FakeEntry.instances[0].set_text("Ada")
    _press(_button_with_text(face_password_gui.PASSWORD_LOGIN_TEXT).command)

    assert runner.calls == []
    assert FakeToplevel.instances[0].destroy_calls == 0


def test_close_paths_return_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)

    assert _run() == 0
    window = FakeToplevel.instances[0]
    assert window.titles == [face_password_gui.PASSWORD_LOGIN_WINDOW_TITLE]
    assert menu_gui.EVENT_CLOSE_WINDOW in window.protocols
    window.protocols[menu_gui.EVENT_CLOSE_WINDOW]()
    window.bindings[menu_gui.EVENT_ESCAPE](None)
    _press(_button_with_text(face_password_gui.PASSWORD_LOGIN_BACK_TEXT).command)

    assert window.destroy_calls == 3
