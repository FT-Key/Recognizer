"""Tests del adaptador de puntero pynput con controlador y pantalla falsos."""

import tkinter

import pytest
from pynput.mouse import Button

from recognizer.adapters.pynput_mouse import PynputMouseController, screen_size
from recognizer.core.errors import ActionError

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
SMALL_EXTENT = 10
ROUNDED_X = 2
ROUNDED_Y = 7
INVALID_SIZE = (0, 100)


class RecordingPositionController:
    """Doble del Controller de pynput que guarda su ultima posicion."""

    def __init__(self) -> None:
        self._position: tuple[int, int] = (-1, -1)
        self.clicks: list[Button] = []

    @property
    def position(self) -> tuple[int, int]:
        return self._position

    @position.setter
    def position(self, value: tuple[int, int]) -> None:
        self._position = value

    def click(self, button: Button) -> None:
        self.clicks.append(button)


class FailingPositionController:
    """Doble cuyo setter de posicion falla con OSError."""

    @property
    def position(self) -> tuple[int, int]:
        return (0, 0)

    @position.setter
    def position(self, value: tuple[int, int]) -> None:
        del value
        msg = "sin mouse"
        raise OSError(msg)

    def click(self, button: Button) -> None:
        del button
        msg = "sin mouse"
        raise OSError(msg)


class ScreenSizeProvider:
    """Provider de tamano de pantalla que cuenta llamadas y puede fallar."""

    def __init__(self, size: tuple[int, int], *, error: OSError | None = None) -> None:
        self.size = size
        self.error = error
        self.calls = 0

    def __call__(self) -> tuple[int, int]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.size


def _mouse(
    controller: RecordingPositionController | FailingPositionController,
    provider: ScreenSizeProvider,
) -> PynputMouseController:
    return PynputMouseController(controller=controller, screen_size=provider)


def test_move_to_maps_corners_to_pixel_range() -> None:
    controller = RecordingPositionController()
    mouse = _mouse(controller, ScreenSizeProvider((SCREEN_WIDTH, SCREEN_HEIGHT)))

    mouse.move_to(x=0.0, y=0.0)
    assert controller.position == (0, 0)

    mouse.move_to(x=1.0, y=1.0)
    assert controller.position == (SCREEN_WIDTH - 1, SCREEN_HEIGHT - 1)


def test_move_to_rounds_intermediate_values() -> None:
    controller = RecordingPositionController()
    mouse = _mouse(controller, ScreenSizeProvider((SMALL_EXTENT, SMALL_EXTENT)))

    mouse.move_to(x=0.25, y=0.75)

    assert controller.position == (ROUNDED_X, ROUNDED_Y)


def test_move_to_clamps_values_outside_unit_range() -> None:
    controller = RecordingPositionController()
    mouse = _mouse(controller, ScreenSizeProvider((SMALL_EXTENT, SMALL_EXTENT)))

    mouse.move_to(x=-0.5, y=1.5)

    assert controller.position == (0, SMALL_EXTENT - 1)


def test_screen_size_provider_is_called_once() -> None:
    provider = ScreenSizeProvider((SCREEN_WIDTH, SCREEN_HEIGHT))
    controller = RecordingPositionController()
    mouse = _mouse(controller, provider)

    mouse.move_to(x=0.0, y=0.0)
    mouse.move_to(x=1.0, y=1.0)

    assert provider.calls == 1


def test_screen_size_provider_error_becomes_action_error() -> None:
    provider = ScreenSizeProvider((SCREEN_WIDTH, SCREEN_HEIGHT), error=OSError("sin pantalla"))
    controller = RecordingPositionController()
    mouse = _mouse(controller, provider)

    with pytest.raises(ActionError, match="No se pudo mover el puntero"):
        mouse.move_to(x=0.5, y=0.5)


def test_missing_screen_module_becomes_action_error() -> None:
    def raise_import_error() -> tuple[int, int]:
        msg = "No module named 'tkinter'"
        raise ModuleNotFoundError(msg)

    mouse = PynputMouseController(
        controller=RecordingPositionController(),
        screen_size=raise_import_error,
    )

    with pytest.raises(ActionError, match="No se pudo mover el puntero"):
        mouse.move_to(x=0.5, y=0.5)


def test_invalid_screen_size_becomes_action_error() -> None:
    controller = RecordingPositionController()
    mouse = _mouse(controller, ScreenSizeProvider(INVALID_SIZE))

    with pytest.raises(ActionError, match="No se pudo mover el puntero"):
        mouse.move_to(x=0.5, y=0.5)


def test_controller_error_becomes_action_error() -> None:
    mouse = _mouse(
        FailingPositionController(),
        ScreenSizeProvider((SCREEN_WIDTH, SCREEN_HEIGHT)),
    )

    with pytest.raises(ActionError, match="No se pudo mover el puntero"):
        mouse.move_to(x=0.5, y=0.5)


def test_click_presses_left_button() -> None:
    controller = RecordingPositionController()
    mouse = _mouse(controller, ScreenSizeProvider((SCREEN_WIDTH, SCREEN_HEIGHT)))

    mouse.click()

    assert controller.clicks == [Button.left]


def test_click_error_becomes_action_error() -> None:
    mouse = _mouse(
        FailingPositionController(),
        ScreenSizeProvider((SCREEN_WIDTH, SCREEN_HEIGHT)),
    )

    with pytest.raises(ActionError, match="No se pudo realizar el click"):
        mouse.click()


def test_default_screen_size_uses_tkinter(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeRoot:
        """Doble de la raiz de tkinter, sin abrir ninguna ventana."""

        def withdraw(self) -> None:
            pass

        def destroy(self) -> None:
            pass

        def winfo_screenwidth(self) -> int:
            return SCREEN_WIDTH

        def winfo_screenheight(self) -> int:
            return SCREEN_HEIGHT

    monkeypatch.setattr(tkinter, "Tk", FakeRoot)
    controller = RecordingPositionController()
    mouse = PynputMouseController(controller=controller)

    mouse.move_to(x=1.0, y=1.0)

    assert controller.position == (SCREEN_WIDTH - 1, SCREEN_HEIGHT - 1)


def test_screen_size_helper_returns_default_size(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeRoot:
        """Doble de la raiz de tkinter, sin abrir ninguna ventana."""

        def withdraw(self) -> None:
            pass

        def destroy(self) -> None:
            pass

        def winfo_screenwidth(self) -> int:
            return SCREEN_WIDTH

        def winfo_screenheight(self) -> int:
            return SCREEN_HEIGHT

    monkeypatch.setattr(tkinter, "Tk", FakeRoot)

    assert screen_size() == (SCREEN_WIDTH, SCREEN_HEIGHT)
