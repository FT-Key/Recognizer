"""Dialogo grafico de login con clave (imperative shell) vintage.

Ventana independiente para iniciar sesion con usuario (ID o DNI) y clave, como
respaldo cuando la camara no funciona o el reconocimiento facial falla. Se abre
desde el submenu facial (``face_menu_gui``) con import perezoso; ``tkinter`` y
el runner se cargan solo al usarse. Enter equivale a ``Ingresar``; si las
credenciales fallan se muestra el error en rojo en el dialogo y se puede
reintentar sin volver al submenu.

Testabilidad: ``tk_factory`` inyecta el ``Toplevel``; los tests parchean
``tkinter.Frame/Label/Button/Entry``. El runner recibe un lector en cola con las
respuestas ``[usuario, clave]`` y devuelve 0 si entro.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING, Protocol

from recognizer.cli import menu_gui
from recognizer.core.constants import FACE_LOGIN_PASSWORD_PROMPT, FACE_LOGIN_USER_PROMPT
from recognizer.core.domain.app import AppRunRequest

if TYPE_CHECKING:
    import tkinter

LOGGER = logging.getLogger("recognizer.menu.face.password")

PASSWORD_LOGIN_WINDOW_TITLE = "Iniciar sesion con clave"
PASSWORD_LOGIN_HEADER_TITLE = "ENTRAR CON CLAVE"
PASSWORD_LOGIN_HEADER_SUBTITLE = "respaldo si la camara o el rostro fallan"
PASSWORD_LOGIN_USER_LABEL = "ID o DNI"
PASSWORD_LOGIN_PASSWORD_LABEL = "Clave"
PASSWORD_LOGIN_TEXT = "Ingresar"
PASSWORD_LOGIN_BACK_TEXT = "Volver"
PASSWORD_LOGIN_FOOTER_HINT = "Enter: ingresar · ESC: volver"
PASSWORD_LOGIN_EMPTY_MESSAGE = "Escribe tu ID o DNI y tu clave."
PASSWORD_LOGIN_FAILED_MESSAGE = "Usuario o clave incorrectos. Intenta de nuevo."
PASSWORD_LOGIN_START_LOG = "Iniciando sesion con clave... (ESC/q para volver)"
PASSWORD_LOGIN_READ_ERROR = "No se pudo leer las credenciales (%s)."
PASSWORD_LOGIN_FOCUS_ERROR = "Sin foco inicial del usuario (%s)."


class PasswordLoginRunner(Protocol):
    """Runner de login por clave con lector inyectable (cola usuario+clave)."""

    def __call__(self, request: AppRunRequest, *, reader: Callable[[str], str]) -> int:
        """Inicia sesion con usuario y clave; devuelve 0 si entro."""
        ...


def _default_password_runner() -> PasswordLoginRunner:
    """Runner real de login por clave (liviano, sin camara)."""
    from recognizer.cli.apps.face_auth import run_face_login_password

    return run_face_login_password


def run_password_login(
    request: AppRunRequest,
    *,
    tk_factory: Callable[[], tkinter.Toplevel] | None = None,
    password_runner: PasswordLoginRunner | None = None,
    logger: logging.Logger = LOGGER,
) -> int:
    """Muestra el dialogo de login por clave y devuelve 0 al cerrarlo.

    ``Ingresar`` oculta la ventana, corre el runner con un lector en cola
    (``[usuario, clave]``) y al terminar destruye la ventana. ``Volver``/X/ESC
    cierran sin autenticar.
    """
    import tkinter

    theme = menu_gui.DEFAULT_THEME
    tk_cls = tk_factory if tk_factory is not None else tkinter.Toplevel
    window = tk_cls()
    window.title(PASSWORD_LOGIN_WINDOW_TITLE)
    window.configure(bg=theme.surface)
    body_family = theme.font_body

    def _make_button(
        parent: tkinter.Frame,
        text: str,
        action: Callable[[], None],
        *,
        primary: bool,
    ) -> tkinter.Button:
        """Boton vintage con el mismo estilo del menu principal."""
        return tkinter.Button(
            parent,
            text=text,
            command=action,
            relief=menu_gui.RELIEF_RAISED,
            bd=menu_gui.BUTTON_BORDER_WIDTH,
            padx=theme.pad_button_x,
            pady=theme.space_1,
            font=(body_family, theme.size_body, menu_gui.FONT_WEIGHT_BOLD),
            bg=theme.primary if primary else theme.surface_alt,
            fg=theme.primary_contrast if primary else theme.text,
            activebackground=theme.primary_strong if primary else theme.surface,
            activeforeground=theme.primary_contrast if primary else theme.text,
            cursor=menu_gui.CURSOR_HAND,
            takefocus=True,
            highlightthickness=menu_gui.FOCUS_HIGHLIGHT_WIDTH,
            highlightbackground=theme.surface_alt,
            highlightcolor=theme.primary_strong,
        )

    def _consume(action: Callable[[], None]) -> Callable[[tkinter.Event], str]:
        def handler(_event: tkinter.Event) -> str:
            action()
            return menu_gui.TK_BREAK

        return handler

    header = tkinter.Frame(window, bg=theme.primary)
    header.pack(side=menu_gui.SIDE_TOP, fill=menu_gui.FILL_X)
    tkinter.Label(
        header,
        text=PASSWORD_LOGIN_HEADER_TITLE,
        font=(body_family, theme.size_display_small, menu_gui.FONT_WEIGHT_BOLD),
        fg=theme.primary_contrast,
        bg=theme.primary,
        anchor=menu_gui.ANCHOR_WEST,
    ).pack(fill=menu_gui.FILL_X)
    tkinter.Label(
        header,
        text=PASSWORD_LOGIN_HEADER_SUBTITLE,
        font=(body_family, theme.size_body_small),
        fg=theme.primary_contrast,
        bg=theme.primary,
        anchor=menu_gui.ANCHOR_WEST,
    ).pack(fill=menu_gui.FILL_X)

    body = tkinter.Frame(window, bg=theme.surface)
    body.pack(
        side=menu_gui.SIDE_TOP,
        fill=menu_gui.FILL_BOTH,
        expand=True,
        padx=theme.pad_body,
        pady=theme.space_4,
    )
    tkinter.Label(
        body,
        text=PASSWORD_LOGIN_USER_LABEL,
        font=(body_family, theme.size_body, menu_gui.FONT_WEIGHT_BOLD),
        fg=theme.text,
        bg=theme.surface,
        anchor=menu_gui.ANCHOR_WEST,
    ).pack(fill=menu_gui.FILL_X)
    user_entry = tkinter.Entry(body)
    user_entry.pack(fill=menu_gui.FILL_X, pady=(menu_gui.BORDER_NONE, theme.space_2))
    tkinter.Label(
        body,
        text=PASSWORD_LOGIN_PASSWORD_LABEL,
        font=(body_family, theme.size_body, menu_gui.FONT_WEIGHT_BOLD),
        fg=theme.text,
        bg=theme.surface,
        anchor=menu_gui.ANCHOR_WEST,
    ).pack(fill=menu_gui.FILL_X)
    password_entry = tkinter.Entry(body, show=menu_gui.PASSWORD_SHOW)
    password_entry.pack(fill=menu_gui.FILL_X, pady=(menu_gui.BORDER_NONE, theme.space_2))
    error_label = tkinter.Label(
        body,
        text="",
        font=(body_family, theme.size_body_small, menu_gui.FONT_WEIGHT_BOLD),
        fg=theme.danger,
        bg=theme.surface,
        anchor=menu_gui.ANCHOR_WEST,
    )
    error_label.pack(fill=menu_gui.FILL_X, pady=(theme.space_1, menu_gui.BORDER_NONE))

    def _fail(message: str) -> None:
        """Muestra el error en el dialogo (rojo) y lo registra."""
        logger.error("%s", message)
        try:
            error_label.configure(text=message)
        except Exception as exc:  # el fake puede no soportar `text`
            logger.debug("Sin etiqueta de error en login por clave (%s).", exc)

    def do_login() -> None:
        try:
            user = user_entry.get().strip()
            password = password_entry.get()
        except Exception as exc:  # el fake o Tk sin display pueden fallar
            logger.warning(PASSWORD_LOGIN_READ_ERROR, exc)
            return
        if not user or not password:
            _fail(PASSWORD_LOGIN_EMPTY_MESSAGE)
            return
        answers = {
            FACE_LOGIN_USER_PROMPT: user,
            FACE_LOGIN_PASSWORD_PROMPT: password,
        }

        def queue_reader(prompt: str) -> str:
            return answers.get(prompt, "")

        runner = password_runner if password_runner is not None else _default_password_runner()
        logger.info(PASSWORD_LOGIN_START_LOG)
        # Sin camara el runner es instantaneo: no se oculta la ventana. Si
        # falla, el dialogo sigue abierto con el error para reintentar.
        if runner(replace(request), reader=queue_reader) != 0:
            _fail(PASSWORD_LOGIN_FAILED_MESSAGE)
            return
        window.destroy()

    def close() -> None:
        window.destroy()

    footer = tkinter.Frame(window, bg=theme.surface_alt)
    footer.pack(side=menu_gui.SIDE_BOTTOM, fill=menu_gui.FILL_X)
    tkinter.Label(
        footer,
        text=PASSWORD_LOGIN_FOOTER_HINT,
        font=(body_family, theme.size_body_small),
        fg=theme.text_muted,
        bg=theme.surface_alt,
        anchor=menu_gui.ANCHOR_WEST,
    ).pack(side=menu_gui.SIDE_LEFT, padx=theme.pad_footer, pady=theme.pad_footer)
    back_button = _make_button(footer, PASSWORD_LOGIN_BACK_TEXT, close, primary=False)
    back_button.pack(side=menu_gui.SIDE_RIGHT, padx=theme.pad_footer, pady=theme.pad_footer)

    actions = tkinter.Frame(window, bg=theme.surface)
    actions.pack(fill=menu_gui.FILL_X, padx=theme.pad_body, pady=theme.space_2)
    login_button = _make_button(actions, PASSWORD_LOGIN_TEXT, do_login, primary=True)
    login_button.pack(side=menu_gui.SIDE_LEFT, padx=theme.space_1)
    try:
        user_entry.focus_set()
    except Exception as exc:  # los fakes o Tk sin display pueden no enfocar
        logger.debug(PASSWORD_LOGIN_FOCUS_ERROR, exc)

    login_button.bind(menu_gui.EVENT_RETURN, _consume(do_login))
    login_button.bind(menu_gui.EVENT_SPACE, _consume(do_login))
    back_button.bind(menu_gui.EVENT_RETURN, _consume(close))
    back_button.bind(menu_gui.EVENT_SPACE, _consume(close))

    window.protocol(menu_gui.EVENT_CLOSE_WINDOW, close)
    # Enter en cualquier campo equivale a Ingresar (los botones consumen su
    # propio Return con `break`, asi que no hay doble disparo).
    window.bind(menu_gui.EVENT_RETURN, _consume(do_login))
    window.bind(menu_gui.EVENT_ESCAPE, lambda _event: close())
    window.bind(menu_gui.EVENT_KEY_Q, lambda _event: close())
    window.bind(menu_gui.EVENT_KEY_Q_UPPER, lambda _event: close())

    try:
        window.wait_window()
    except KeyboardInterrupt:
        logger.info("Interrumpido; volviendo al submenu.")
    return 0
