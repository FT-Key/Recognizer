"""Submenu grafico de reconocimiento facial (imperative shell) vintage.

Se abre desde el menu grafico cuando se elige ``FACE_AUTH``; la consola
(``run_face_auth`` en ``cli/apps/face_auth.py``) sigue como fallback con
``--no-gui``. ``tkinter`` y los runners de vision se importan dentro de las
funciones para no cargar modelos al abrir el menu.

Testabilidad (fakes necesarios)
-------------------------------
Los tests inyectan ``tk_factory`` (fabrica del ``Toplevel``) y parchean
``tkinter.Frame/Label/Button/Entry/OptionMenu/StringVar``:

- ``Toplevel`` (via ``tk_factory``): doble con ``title``, ``configure``,
  ``protocol``, ``bind``, ``withdraw``, ``deiconify``, ``destroy`` y
  ``mainloop``.
- ``Entry``: doble con ``get``, ``pack`` y ``focus_set``.
- ``StringVar``: doble con ``get`` y ``set``.
- ``OptionMenu``: doble no-op con ``pack``.
- ``Frame``/``Label``/``Button``: como en ``menu_gui`` (``Button`` registra
  su ``command``).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING, Protocol

from recognizer.cli import menu_gui
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.domain.identity import Role
from recognizer.core.ports.identity_provider import IdentityProvider

if TYPE_CHECKING:
    import tkinter

LOGGER = logging.getLogger("recognizer.menu.face")

FACE_SUBMENU_TITLE = "Reconocimiento facial"
FACE_HEADER_TITLE = "RECONOCIMIENTO FACIAL"
FACE_HEADER_SUBTITLE = "enrola tu cara o inicia sesion"
FACE_NAME_LABEL = "Nombre"
FACE_ROLE_LABEL = "Rol"
FACE_ENROLL_TEXT = "Enrolar"
FACE_LOGIN_TEXT = "Login"
FACE_LOGOUT_TEXT = "Cerrar sesión"
FACE_BACK_TEXT = "Volver"
FACE_FIRST_NOTE_TEXT = "nota: el primer rostro = admin"
FACE_NO_PERMISSION_TEXT = "sin permiso: se requiere operator o admin"
FACE_FOOTER_HINT = "Enter: activar · ESC: volver"
FACE_EMPTY_NAME_MESSAGE = "Enrolamiento cancelado: escribe un nombre primero."
FACE_CURRENT_ROLE_TEMPLATE = "Sesión: {name} ({role})"

QueueReader = Callable[[str], str]


class EnrollRunner(Protocol):
    """Runner de enrolamiento con lector inyectable (cola nombre+rol en GUI)."""

    def __call__(self, request: AppRunRequest, *, reader: QueueReader | None = ...) -> int:
        """Enrola un rostro; devuelve 0 si termino bien."""
        ...


class FaceActionRunner(Protocol):
    """Runner facial sin lector (login/logout)."""

    def __call__(self, request: AppRunRequest) -> int:
        """Ejecuta la accion; devuelve 0 si termino bien."""
        ...


def _allowed_roles(*, is_first: bool, role: Role) -> tuple[Role, ...]:
    """Roles enrolables segun el almacen y el rol del operador actual."""
    if is_first:
        return (Role.ADMIN,)
    match role:
        case Role.ADMIN:
            return (Role.ADMIN, Role.OPERATOR, Role.VIEWER)
        case Role.OPERATOR:
            return (Role.OPERATOR, Role.VIEWER)
        case _:
            return ()


def _default_provider(request: AppRunRequest, *, logger: logging.Logger) -> IdentityProvider:
    """Proveedor de sesion liviano (solo stdlib+json, sin modelos de vision)."""
    from recognizer.adapters.file_face_repository import FileFaceRepository
    from recognizer.adapters.file_identity_provider import (
        AllowAllIdentityProvider,
        FileIdentityProvider,
    )
    from recognizer.core.errors import ConfigError
    from recognizer.settings import load_config

    try:
        app_config = load_config(request.config_path)
    except ConfigError as exc:
        logger.warning("Sin config facial (%s); sesion invitada.", exc)
        return AllowAllIdentityProvider()
    try:
        repository = FileFaceRepository(app_config.face_auth.store_dir)
    except OSError as exc:
        logger.warning("Almacen facial no disponible (%s); sesion invitada.", exc)
        return AllowAllIdentityProvider()
    return FileIdentityProvider(
        app_config.face_auth.store_dir,
        repository,
        session_timeout_seconds=app_config.face_auth.session_timeout_seconds,
    )


def _store_is_empty(provider: IdentityProvider) -> bool:
    """Indica si el almacen facial esta vacio (primer rostro = admin)."""
    from recognizer.adapters.file_face_repository import FileFaceRepository
    from recognizer.adapters.file_identity_provider import FileIdentityProvider

    if not isinstance(provider, FileIdentityProvider):
        return False
    try:
        repository = FileFaceRepository(provider.store_dir)
    except OSError:
        return False
    try:
        return len(repository.list_all()) == 0
    except OSError:
        return False


def _default_enroll_runner() -> EnrollRunner:
    """Runner real de enrolamiento (import perezoso: carga InsightFace)."""
    from recognizer.cli.apps.face_auth import run_face_enroll

    return run_face_enroll


def _default_login_runner() -> FaceActionRunner:
    """Runner real de login (import perezoso: carga InsightFace)."""
    from recognizer.cli.apps.face_auth import run_face_login

    return run_face_login


def _default_logout_runner() -> FaceActionRunner:
    """Runner real de logout (liviano, sin camara)."""
    from recognizer.cli.apps.face_auth import run_face_logout

    return run_face_logout


def run_face_submenu(
    request: AppRunRequest,
    *,
    tk_factory: Callable[[], tkinter.Toplevel] | None = None,
    enroll_runner: EnrollRunner | None = None,
    login_runner: FaceActionRunner | None = None,
    logout_runner: FaceActionRunner | None = None,
    identity_provider: IdentityProvider | None = None,
    logger: logging.Logger = LOGGER,
) -> int:
    """Muestra el submenu facial vintage y devuelve 0 al cerrarlo.

    ``Enrolar`` oculta la ventana, corre el runner con un lector en cola que
    devuelve ``[nombre, rol]`` en orden y al terminar re-muestra la ventana y
    refresca el rol visible. ``Login``/``Logout`` igual sin lector.
    ``Volver``/X/ESC destruye la ventana y devuelve 0.
    """
    import tkinter

    theme = menu_gui.DEFAULT_THEME
    provider = (
        identity_provider
        if identity_provider is not None
        else _default_provider(request, logger=logger)
    )
    state: dict[str, object] = {}
    current = provider.current_identity()
    state["role"] = current.role
    state["name"] = current.name
    state["is_first"] = _store_is_empty(provider)
    state["allowed"] = _allowed_roles(is_first=bool(state["is_first"]), role=current.role)
    raw_allowed = state["allowed"]
    allowed = raw_allowed if isinstance(raw_allowed, tuple) else ()
    is_first = bool(state["is_first"])

    tk_cls = tk_factory if tk_factory is not None else tkinter.Toplevel
    window = tk_cls()
    window.title(FACE_SUBMENU_TITLE)
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
        text=FACE_HEADER_TITLE,
        font=(body_family, theme.size_display_small, menu_gui.FONT_WEIGHT_BOLD),
        fg=theme.primary_contrast,
        bg=theme.primary,
        anchor=menu_gui.ANCHOR_WEST,
    ).pack(fill=menu_gui.FILL_X)
    tkinter.Label(
        header,
        text=FACE_HEADER_SUBTITLE,
        font=(body_family, theme.size_body_small),
        fg=theme.primary_contrast,
        bg=theme.primary,
        anchor=menu_gui.ANCHOR_WEST,
    ).pack(fill=menu_gui.FILL_X)
    role_label = tkinter.Label(
        header,
        text=FACE_CURRENT_ROLE_TEMPLATE.format(name=current.name, role=current.role.value),
        font=(body_family, theme.size_body_small),
        fg=theme.primary_contrast,
        bg=theme.primary,
        anchor=menu_gui.ANCHOR_WEST,
    )
    role_label.pack(fill=menu_gui.FILL_X)

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
        text=FACE_NAME_LABEL,
        font=(body_family, theme.size_body, menu_gui.FONT_WEIGHT_BOLD),
        fg=theme.text,
        bg=theme.surface,
        anchor=menu_gui.ANCHOR_WEST,
    ).pack(fill=menu_gui.FILL_X)
    name_entry = tkinter.Entry(body)
    name_entry.pack(fill=menu_gui.FILL_X)
    try:
        name_entry.focus_set()
    except Exception as exc:  # los fakes o Tk sin display pueden no enfocar
        logger.debug("Sin foco inicial del nombre (%s).", exc)

    tkinter.Label(
        body,
        text=FACE_ROLE_LABEL,
        font=(body_family, theme.size_body, menu_gui.FONT_WEIGHT_BOLD),
        fg=theme.text,
        bg=theme.surface,
        anchor=menu_gui.ANCHOR_WEST,
    ).pack(fill=menu_gui.FILL_X)
    role_var = tkinter.StringVar()
    if allowed:
        role_var.set(allowed[0].value)
        tkinter.OptionMenu(body, role_var, *(role.value for role in allowed))
    else:
        tkinter.Label(
            body,
            text=FACE_NO_PERMISSION_TEXT,
            font=(body_family, theme.size_body_small),
            fg=theme.text_muted,
            bg=theme.surface,
            anchor=menu_gui.ANCHOR_WEST,
        ).pack(fill=menu_gui.FILL_X)
    if is_first:
        tkinter.Label(
            body,
            text=FACE_FIRST_NOTE_TEXT,
            font=(body_family, theme.size_body_small),
            fg=theme.text_muted,
            bg=theme.surface,
            anchor=menu_gui.ANCHOR_WEST,
        ).pack(fill=menu_gui.FILL_X)

    footer = tkinter.Frame(window, bg=theme.surface_alt)
    footer.pack(side=menu_gui.SIDE_BOTTOM, fill=menu_gui.FILL_X)
    tkinter.Label(
        footer,
        text=FACE_FOOTER_HINT,
        font=(body_family, theme.size_body_small),
        fg=theme.text_muted,
        bg=theme.surface_alt,
        anchor=menu_gui.ANCHOR_WEST,
    ).pack(side=menu_gui.SIDE_LEFT, padx=theme.pad_footer, pady=theme.pad_footer)

    def refresh_permissions() -> tuple[Role, ...]:
        """Relee la sesion y recalcula permisos; el gate siempre usa datos frescos."""
        fresh = provider.refresh()
        fresh_first = _store_is_empty(provider)
        fresh_allowed = _allowed_roles(is_first=fresh_first, role=fresh.role)
        state["role"] = fresh.role
        state["name"] = fresh.name
        state["is_first"] = fresh_first
        state["allowed"] = fresh_allowed
        try:
            role_label.configure(
                text=FACE_CURRENT_ROLE_TEMPLATE.format(name=fresh.name, role=fresh.role.value)
            )
        except Exception as exc:  # el refresco jamas tumba el submenu
            logger.debug("No se pudo refrescar el rol visible (%s).", exc)
        if fresh_allowed:
            try:
                if role_var.get().strip().lower() not in {role.value for role in fresh_allowed}:
                    role_var.set(fresh_allowed[0].value)
            except Exception as exc:
                logger.debug("No se pudo ajustar el rol elegido (%s).", exc)
        return fresh_allowed

    def refresh_role() -> None:
        """Relee la sesion y refresca el rol visible de la cabecera."""
        refresh_permissions()

    def do_enroll() -> None:
        fresh_allowed = refresh_permissions()
        if not fresh_allowed:
            current_role = state["role"]
            role_name = current_role.value if isinstance(current_role, Role) else "?"
            logger.warning("Sin permiso para enrolar (tu rol: %s).", role_name)
            return
        try:
            name = name_entry.get().strip()
        except Exception as exc:
            logger.warning("No se pudo leer el nombre (%s).", exc)
            return
        if not name:
            logger.error(FACE_EMPTY_NAME_MESSAGE)
            return
        try:
            role_text = role_var.get().strip().lower()
        except Exception as exc:
            logger.debug("Sin rol elegido (%s); se usa el primero permitido.", exc)
            role_text = fresh_allowed[0].value
        if role_text not in {role.value for role in fresh_allowed}:
            logger.warning("Rol no permitido %r; se usa %s.", role_text, fresh_allowed[0].value)
            role_text = fresh_allowed[0].value
        queue: list[str] = [name, role_text]

        def queue_reader(_prompt: str) -> str:
            return queue.pop(0) if queue else ""

        runner = enroll_runner if enroll_runner is not None else _default_enroll_runner()
        logger.info("Enrolando '%s'... (ESC/q para volver)", name)
        window.withdraw()
        try:
            runner(replace(request), reader=queue_reader)
        finally:
            window.deiconify()
        refresh_role()

    def do_login() -> None:
        runner = login_runner if login_runner is not None else _default_login_runner()
        logger.info("Login facial... (ESC/q para volver)")
        window.withdraw()
        try:
            runner(replace(request))
        finally:
            window.deiconify()
        refresh_role()

    def do_logout() -> None:
        runner = logout_runner if logout_runner is not None else _default_logout_runner()
        window.withdraw()
        try:
            runner(replace(request))
        finally:
            window.deiconify()
        refresh_role()

    def close() -> None:
        window.destroy()

    enroll_button = _make_button(body, FACE_ENROLL_TEXT, do_enroll, primary=True)
    enroll_button.pack(side=menu_gui.SIDE_LEFT, padx=theme.space_1, pady=theme.space_2)
    login_button = _make_button(body, FACE_LOGIN_TEXT, do_login, primary=False)
    login_button.pack(side=menu_gui.SIDE_LEFT, padx=theme.space_1, pady=theme.space_2)
    logout_button = _make_button(body, FACE_LOGOUT_TEXT, do_logout, primary=False)
    logout_button.pack(side=menu_gui.SIDE_LEFT, padx=theme.space_1, pady=theme.space_2)
    back_button = _make_button(footer, FACE_BACK_TEXT, close, primary=False)
    back_button.pack(side=menu_gui.SIDE_RIGHT, padx=theme.pad_footer, pady=theme.pad_footer)
    for button, action in (
        (enroll_button, do_enroll),
        (login_button, do_login),
        (logout_button, do_logout),
        (back_button, close),
    ):
        button.bind(menu_gui.EVENT_RETURN, _consume(action))
        button.bind(menu_gui.EVENT_SPACE, _consume(action))

    window.protocol(menu_gui.EVENT_CLOSE_WINDOW, close)
    window.bind(menu_gui.EVENT_ESCAPE, lambda _event: close())
    window.bind(menu_gui.EVENT_KEY_Q, lambda _event: close())
    window.bind(menu_gui.EVENT_KEY_Q_UPPER, lambda _event: close())

    try:
        window.mainloop()
    except KeyboardInterrupt:
        logger.info("Interrumpido; volviendo al menu.")
    return 0
