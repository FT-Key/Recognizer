"""Formulario grafico de enrolamiento facial (imperative shell) vintage.

Ventana independiente que pide nombre y rol y lanza el runner de enrolamiento
con un lector en cola (``[nombre, rol]``). Se abre desde el submenu facial
(``face_menu_gui``) con import perezoso; ``tkinter`` y los modelos de vision
tambien se cargan solo al usarse.

Testabilidad (fakes necesarios)
------------------------------
Los tests inyectan ``tk_factory`` (fabrica del ``Toplevel``) y parchean
``tkinter.Frame/Label/Button/Entry/OptionMenu/StringVar``:

- ``Toplevel`` (via ``tk_factory``): doble con ``title``, ``configure``,
  ``protocol``, ``bind``, ``withdraw``, ``deiconify``, ``destroy`` y
  ``wait_window``.
- ``Entry``: doble con ``get``, ``pack`` y ``focus_set``.
- ``StringVar``: doble con ``get`` y ``set``.
- ``OptionMenu``: doble no-op con ``pack``/``configure``.
- ``Frame``/``Label``/``Button``: como en ``menu_gui`` (``Button`` registra
  su ``command`` y expone ``pack``/``pack_forget``).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING, Protocol

from recognizer.cli import menu_gui
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.ports.identity_provider import IdentityProvider

if TYPE_CHECKING:
    import tkinter

LOGGER = logging.getLogger("recognizer.menu.face.enroll")

ENROLL_WINDOW_TITLE = "Enrolamiento facial"
ENROLL_HEADER_TITLE = "ENROLAR"
ENROLL_HEADER_SUBTITLE = "asigna nombre y rol al nuevo rostro"
ENROLL_NAME_LABEL = "Nombre"
ENROLL_ROLE_LABEL = "Rol"
ENROLL_TEXT = "Enrolar"
ENROLL_BACK_TEXT = "Volver"
ENROLL_FIRST_NOTE_TEXT = "nota: el primer rostro = admin"
ENROLL_NO_PERMISSION_TEXT = "sin permiso: se requiere operator o admin"
ENROLL_FOOTER_HINT = "Enter: activar · ESC: volver"
ENROLL_EMPTY_NAME_MESSAGE = "Enrolamiento cancelado: escribe un nombre primero."
ENROLL_START_LOG = "Enrolando '%s'... (ESC/q para volver)"
ENROLL_ROLE_FALLBACK_LOG = "Rol no permitido %r; se usa %s."
ENROLL_NAME_READ_ERROR = "No se pudo leer el nombre (%s)."
ENROLL_ROLE_READ_ERROR = "Sin rol elegido (%s); se usa el primero permitido."
ENROLL_DISABLE_ERROR = "No se pudo deshabilitar Enrolar (%s)."
ENROLL_FOCUS_ERROR = "Sin foco inicial del nombre (%s)."

QueueReader = Callable[[str], str]


class EnrollRunner(Protocol):
    """Runner de enrolamiento con lector inyectable (cola nombre+rol en GUI)."""

    def __call__(self, request: AppRunRequest, *, reader: QueueReader | None = ...) -> int:
        """Enrola un rostro; devuelve 0 si termino bien."""
        ...


def _default_enroll_runner() -> EnrollRunner:
    """Runner real de enrolamiento (import perezoso: carga InsightFace)."""
    from recognizer.cli.apps.face_auth import run_face_enroll

    return run_face_enroll


def run_enroll_form(
    request: AppRunRequest,
    *,
    tk_factory: Callable[[], tkinter.Toplevel] | None = None,
    identity_provider: IdentityProvider | None = None,
    enroll_runner: EnrollRunner | None = None,
    logger: logging.Logger = LOGGER,
) -> int:
    """Muestra el formulario de enrolamiento y devuelve 0 al cerrarlo.

    ``Enrolar`` oculta la ventana, corre el runner con un lector en cola que
    devuelve ``[nombre, rol]`` en orden y al terminar destruye la ventana.
    ``Volver``/X/ESC cierran sin enrolar. Si el operador no tiene permiso se
    muestra el aviso y el boton ``Enrolar`` queda deshabilitado.
    """
    import tkinter

    from recognizer.cli.face_adapters import (
        allowed_roles,
        default_enroll_role,
        default_identity_provider,
        store_is_empty,
    )

    theme = menu_gui.DEFAULT_THEME
    provider = (
        identity_provider
        if identity_provider is not None
        else default_identity_provider(request, logger=logger)
    )
    current = provider.current_identity()
    is_first = store_is_empty(provider)
    roles = allowed_roles(is_first=is_first, role=current.role)

    tk_cls = tk_factory if tk_factory is not None else tkinter.Toplevel
    window = tk_cls()
    window.title(ENROLL_WINDOW_TITLE)
    window.configure(bg=theme.surface)
    body_family = theme.font_body

    def _make_button(
        parent: tkinter.Frame,
        text: str,
        action: Callable[[], None],
        *,
        primary: bool,
    ) -> tkinter.Button:
        """Boton vintage con el mismo estilo del menu principal (raised 3px)."""
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
        text=ENROLL_HEADER_TITLE,
        font=(body_family, theme.size_display_small, menu_gui.FONT_WEIGHT_BOLD),
        fg=theme.primary_contrast,
        bg=theme.primary,
        anchor=menu_gui.ANCHOR_WEST,
    ).pack(fill=menu_gui.FILL_X)
    tkinter.Label(
        header,
        text=ENROLL_HEADER_SUBTITLE,
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
        text=ENROLL_NAME_LABEL,
        font=(body_family, theme.size_body, menu_gui.FONT_WEIGHT_BOLD),
        fg=theme.text,
        bg=theme.surface,
        anchor=menu_gui.ANCHOR_WEST,
    ).pack(fill=menu_gui.FILL_X)
    name_entry = tkinter.Entry(body)
    name_entry.pack(fill=menu_gui.FILL_X, pady=(menu_gui.BORDER_NONE, theme.space_2))
    tkinter.Label(
        body,
        text=ENROLL_ROLE_LABEL,
        font=(body_family, theme.size_body, menu_gui.FONT_WEIGHT_BOLD),
        fg=theme.text,
        bg=theme.surface,
        anchor=menu_gui.ANCHOR_WEST,
    ).pack(fill=menu_gui.FILL_X)

    role_var = tkinter.StringVar()
    if roles:
        role_var.set(default_enroll_role(request, roles, logger=logger).value)
        role_option = tkinter.OptionMenu(body, role_var, *(role.value for role in roles))
        # El __init__ de OptionMenu en typeshed no declara los kwargs del
        # Menubutton; se aplican con `configure`, que si los acepta.
        role_option.configure(
            relief=menu_gui.RELIEF_RAISED,
            bd=menu_gui.BUTTON_BORDER_WIDTH,
            font=(body_family, theme.size_body, menu_gui.FONT_WEIGHT_BOLD),
            bg=theme.surface_alt,
            fg=theme.text,
            activebackground=theme.primary_soft,
            activeforeground=theme.text,
            cursor=menu_gui.CURSOR_HAND,
            highlightthickness=menu_gui.FOCUS_HIGHLIGHT_WIDTH,
            highlightbackground=theme.surface,
            highlightcolor=theme.primary_strong,
            anchor=menu_gui.ANCHOR_WEST,
        )
        role_option.pack(fill=menu_gui.FILL_X, pady=theme.space_1)

    if is_first:
        tkinter.Label(
            body,
            text=ENROLL_FIRST_NOTE_TEXT,
            font=(body_family, theme.size_body_small),
            fg=theme.text_muted,
            bg=theme.surface,
            anchor=menu_gui.ANCHOR_WEST,
        ).pack(fill=menu_gui.FILL_X, pady=(menu_gui.BORDER_NONE, theme.space_2))
    if not roles:
        tkinter.Label(
            body,
            text=ENROLL_NO_PERMISSION_TEXT,
            font=(body_family, theme.size_body_small),
            fg=theme.text_muted,
            bg=theme.surface,
            anchor=menu_gui.ANCHOR_WEST,
        ).pack(fill=menu_gui.FILL_X, pady=(menu_gui.BORDER_NONE, theme.space_2))

    def do_enroll() -> None:
        if not roles:
            logger.warning(ENROLL_NO_PERMISSION_TEXT)
            return
        try:
            name = name_entry.get().strip()
        except Exception as exc:  # el fake o Tk sin display pueden fallar
            logger.warning(ENROLL_NAME_READ_ERROR, exc)
            return
        if not name:
            logger.error(ENROLL_EMPTY_NAME_MESSAGE)
            return
        try:
            role_text = role_var.get().strip().lower()
        except Exception as exc:
            logger.debug(ENROLL_ROLE_READ_ERROR, exc)
            role_text = roles[0].value
        if role_text not in {role.value for role in roles}:
            logger.warning(ENROLL_ROLE_FALLBACK_LOG, role_text, roles[0].value)
            role_text = roles[0].value
        queue: list[str] = [name, role_text]

        def queue_reader(_prompt: str) -> str:
            return queue.pop(0) if queue else ""

        runner = enroll_runner if enroll_runner is not None else _default_enroll_runner()
        logger.info(ENROLL_START_LOG, name)
        window.withdraw()
        try:
            runner(replace(request), reader=queue_reader)
        finally:
            window.deiconify()
        window.destroy()

    def close() -> None:
        window.destroy()

    footer = tkinter.Frame(window, bg=theme.surface_alt)
    footer.pack(side=menu_gui.SIDE_BOTTOM, fill=menu_gui.FILL_X)
    tkinter.Label(
        footer,
        text=ENROLL_FOOTER_HINT,
        font=(body_family, theme.size_body_small),
        fg=theme.text_muted,
        bg=theme.surface_alt,
        anchor=menu_gui.ANCHOR_WEST,
    ).pack(side=menu_gui.SIDE_LEFT, padx=theme.pad_footer, pady=theme.pad_footer)
    back_button = _make_button(footer, ENROLL_BACK_TEXT, close, primary=False)
    back_button.pack(side=menu_gui.SIDE_RIGHT, padx=theme.pad_footer, pady=theme.pad_footer)

    actions = tkinter.Frame(window, bg=theme.surface)
    actions.pack(fill=menu_gui.FILL_X, padx=theme.pad_body, pady=theme.space_2)
    enroll_button = _make_button(actions, ENROLL_TEXT, do_enroll, primary=True)
    enroll_button.pack(side=menu_gui.SIDE_LEFT, padx=theme.space_1)
    if not roles:
        try:
            enroll_button.configure(state=menu_gui.STATE_DISABLED)
        except Exception as exc:  # el fake puede no soportar `state`
            logger.debug(ENROLL_DISABLE_ERROR, exc)
    else:
        try:
            name_entry.focus_set()
        except Exception as exc:  # los fakes o Tk sin display pueden no enfocar
            logger.debug(ENROLL_FOCUS_ERROR, exc)

    enroll_button.bind(menu_gui.EVENT_RETURN, _consume(do_enroll))
    enroll_button.bind(menu_gui.EVENT_SPACE, _consume(do_enroll))
    back_button.bind(menu_gui.EVENT_RETURN, _consume(close))
    back_button.bind(menu_gui.EVENT_SPACE, _consume(close))

    window.protocol(menu_gui.EVENT_CLOSE_WINDOW, close)
    window.bind(menu_gui.EVENT_ESCAPE, lambda _event: close())
    window.bind(menu_gui.EVENT_KEY_Q, lambda _event: close())
    window.bind(menu_gui.EVENT_KEY_Q_UPPER, lambda _event: close())

    try:
        # `wait_window` espera SOLO a que se destruya este Toplevel (igual que
        # el submenu): un `mainloop` anidado dejaria el proceso colgado.
        window.wait_window()
    except KeyboardInterrupt:
        logger.info("Interrumpido; volviendo al submenu.")
    return 0
