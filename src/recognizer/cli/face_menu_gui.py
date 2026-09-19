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
  su ``command`` y expone ``pack``/``pack_forget`` para alternar visibilidad).
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
FACE_USERS_TEXT = "Usuarios"
FACE_ACCESS_TEXT = "Accesos"
FACE_MY_ACCESS_TEXT = "Mis accesos"
FACE_BACK_TEXT = "Volver"
FACE_FIRST_NOTE_TEXT = "nota: el primer rostro = admin"
FACE_NO_PERMISSION_TEXT = "sin permiso: se requiere operator o admin"
FACE_FOOTER_HINT = "Enter: activar · ESC: volver"
FACE_EMPTY_NAME_MESSAGE = "Enrolamiento cancelado: escribe un nombre primero."
FACE_CURRENT_ROLE_TEMPLATE = "Sesión: {name} ({role})"
FACE_ENROLL_DENIED_TEMPLATE = "Enrolar oculto: sin permiso (tu rol: {role})."
FACE_USERS_LOG = "Abriendo panel de usuarios... (ESC/q para volver)"
FACE_ACCESS_LOG = "Abriendo panel de accesos... (ESC/q para volver)"

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
    from recognizer.cli.face_adapters import default_identity_provider

    return default_identity_provider(request, logger=logger)


def _default_role(
    request: AppRunRequest, allowed: tuple[Role, ...], *, logger: logging.Logger
) -> Role:
    """Rol preseleccionado al enrolar: el de config si esta permitido.

    Evita que un admin quede seleccionado por defecto (el nuevo usuario saldria
    admin); se usa ``face_auth.default_role`` (operator) salvo que no se permita.
    """
    from recognizer.cli.face_adapters import load_face_config

    config = load_face_config(request, logger=logger)
    if config is not None and config.default_role in allowed:
        return config.default_role
    return allowed[0]


def _store_is_empty(provider: IdentityProvider) -> bool:
    """Indica si el almacen facial esta vacio (primer rostro = admin)."""
    from recognizer.adapters.file_face_repository import FileFaceRepository
    from recognizer.adapters.file_identity_provider import FileIdentityProvider
    from recognizer.core.errors import RecognizerError

    if not isinstance(provider, FileIdentityProvider):
        return False
    try:
        repository = FileFaceRepository(provider.store_dir)
    except (OSError, RecognizerError):
        return False
    try:
        return len(repository.list_all()) == 0
    except (OSError, RecognizerError):
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
    refresca el rol visible. ``Login``/``Logout`` igual sin lector. ``Usuarios``
    (admin) y ``Accesos``/``Mis accesos`` abren sus paneles de forma perezosa
    ocultando la ventana. ``Volver``/X/ESC destruye la ventana y devuelve 0.
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
    state["logged_in"] = bool(current.authenticated_at)
    state["is_admin"] = current.role is Role.ADMIN
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
    # Formulario de enrolamiento (nombre + rol). Solo tiene sentido cuando el
    # usuario puede enrolar; si no, se oculta por completo (los datos no sirven).
    enroll_form = tkinter.Frame(body, bg=theme.surface)
    enroll_form.pack(fill=menu_gui.FILL_X)
    name_label = tkinter.Label(
        enroll_form,
        text=FACE_NAME_LABEL,
        font=(body_family, theme.size_body, menu_gui.FONT_WEIGHT_BOLD),
        fg=theme.text,
        bg=theme.surface,
        anchor=menu_gui.ANCHOR_WEST,
    )
    name_entry = tkinter.Entry(enroll_form)
    role_label = tkinter.Label(
        enroll_form,
        text=FACE_ROLE_LABEL,
        font=(body_family, theme.size_body, menu_gui.FONT_WEIGHT_BOLD),
        fg=theme.text,
        bg=theme.surface,
        anchor=menu_gui.ANCHOR_WEST,
    )
    role_var = tkinter.StringVar()
    role_option: tkinter.OptionMenu | None = None
    role_option_values: tuple[str, ...] = ()
    first_note = tkinter.Label(
        enroll_form,
        text=FACE_FIRST_NOTE_TEXT,
        font=(body_family, theme.size_body_small),
        fg=theme.text_muted,
        bg=theme.surface,
        anchor=menu_gui.ANCHOR_WEST,
    )
    no_permission_label = tkinter.Label(
        enroll_form,
        text=FACE_NO_PERMISSION_TEXT,
        font=(body_family, theme.size_body_small),
        fg=theme.text_muted,
        bg=theme.surface,
        anchor=menu_gui.ANCHOR_WEST,
    )

    def _build_role_option(roles: tuple[Role, ...]) -> tkinter.OptionMenu:
        """Crea (o recrea) el selector de rol con las opciones permitidas."""
        role_var.set(_default_role(request, roles, logger=logger).value)
        option = tkinter.OptionMenu(enroll_form, role_var, *(role.value for role in roles))
        # El __init__ de OptionMenu en typeshed no declara los kwargs del
        # Menubutton; se aplican con `configure`, que si los acepta.
        option.configure(
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
        option.pack(fill=menu_gui.FILL_X)
        return option

    def _sync_enroll_form(roles: tuple[Role, ...], *, first: bool) -> None:
        """Muestra el formulario solo si hay permiso; ajusta el selector de rol."""
        nonlocal role_option, role_option_values
        wanted = tuple(role.value for role in roles)
        if roles:
            name_label.pack(fill=menu_gui.FILL_X)
            name_entry.pack(fill=menu_gui.FILL_X)
            role_label.pack(fill=menu_gui.FILL_X)
            if role_option is None or role_option_values != wanted:
                if role_option is not None:
                    role_option.pack_forget()
                    role_option.destroy()
                role_option = _build_role_option(roles)
                role_option_values = wanted
            no_permission_label.pack_forget()
            if first:
                first_note.pack(fill=menu_gui.FILL_X)
            else:
                first_note.pack_forget()
            try:
                name_entry.focus_set()
            except Exception as exc:  # los fakes o Tk sin display pueden no enfocar
                logger.debug("Sin foco inicial del nombre (%s).", exc)
        else:
            name_label.pack_forget()
            name_entry.pack_forget()
            role_label.pack_forget()
            if role_option is not None:
                role_option.pack_forget()
                role_option.destroy()
                role_option = None
                role_option_values = ()
            first_note.pack_forget()
            no_permission_label.pack(fill=menu_gui.FILL_X)

    _sync_enroll_form(allowed, first=is_first)

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
        state["logged_in"] = bool(fresh.authenticated_at)
        state["is_admin"] = fresh.role is Role.ADMIN
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
        refresh_session()

    def do_login() -> None:
        runner = login_runner if login_runner is not None else _default_login_runner()
        logger.info("Login facial... (ESC/q para volver)")
        window.withdraw()
        try:
            runner(replace(request))
        finally:
            window.deiconify()
        refresh_session()

    def do_logout() -> None:
        runner = logout_runner if logout_runner is not None else _default_logout_runner()
        window.withdraw()
        try:
            runner(replace(request))
        finally:
            window.deiconify()
        refresh_session()

    def do_users() -> None:
        from recognizer.cli.face_users_gui import run_users_panel

        logger.info(FACE_USERS_LOG)
        window.withdraw()
        try:
            run_users_panel(replace(request), identity_provider=provider, logger=logger)
        finally:
            window.deiconify()
        refresh_session()

    def do_access() -> None:
        from recognizer.cli.face_access_gui import run_access_panel

        logger.info(FACE_ACCESS_LOG)
        window.withdraw()
        try:
            run_access_panel(
                replace(request),
                identity=provider.current_identity(),
                show_photos=True,
                logger=logger,
            )
        finally:
            window.deiconify()
        refresh_session()

    def do_my_access() -> None:
        from recognizer.cli.face_access_gui import run_access_panel

        logger.info(FACE_ACCESS_LOG)
        window.withdraw()
        try:
            run_access_panel(
                replace(request),
                identity=provider.current_identity(),
                show_photos=False,
                logger=logger,
            )
        finally:
            window.deiconify()
        refresh_session()

    def close() -> None:
        window.destroy()

    def _show(button: tkinter.Button) -> None:
        button.pack(side=menu_gui.SIDE_LEFT, padx=theme.space_1, pady=theme.space_2)

    def _hide(button: tkinter.Button) -> None:
        button.pack_forget()

    enroll_button = _make_button(body, FACE_ENROLL_TEXT, do_enroll, primary=True)
    login_button = _make_button(body, FACE_LOGIN_TEXT, do_login, primary=False)
    logout_button = _make_button(body, FACE_LOGOUT_TEXT, do_logout, primary=False)
    users_button = _make_button(body, FACE_USERS_TEXT, do_users, primary=False)
    access_button = _make_button(body, FACE_ACCESS_TEXT, do_access, primary=False)
    my_access_button = _make_button(body, FACE_MY_ACCESS_TEXT, do_my_access, primary=False)
    back_button = _make_button(footer, FACE_BACK_TEXT, close, primary=False)
    back_button.pack(side=menu_gui.SIDE_RIGHT, padx=theme.pad_footer, pady=theme.pad_footer)

    def refresh_session_ui() -> None:
        """Muestra u oculta los botones segun la sesion y el rol vigentes.

        Se crean siempre todos los botones y aqui se alterna su visibilidad con
        ``pack``/``pack_forget``: asi el usuario solo ve las acciones que puede
        hacer (Enrolar con permiso, Login sin sesion, Logout con sesion,
        Usuarios/Accesos solo admin, Mis accesos solo no-admin autenticado).
        """
        fresh = provider.current_identity()
        logged_in = bool(fresh.authenticated_at)
        is_admin = fresh.role is Role.ADMIN
        state["logged_in"] = logged_in
        state["is_admin"] = is_admin
        raw_allowed = state["allowed"]
        allowed_now = raw_allowed if isinstance(raw_allowed, tuple) else ()
        _sync_enroll_form(allowed_now, first=bool(state["is_first"]))
        if allowed_now:
            _show(enroll_button)
        else:
            _hide(enroll_button)
            logger.warning(FACE_ENROLL_DENIED_TEMPLATE.format(role=fresh.role.value))
        if logged_in:
            _hide(login_button)
            _show(logout_button)
        else:
            _show(login_button)
            _hide(logout_button)
        if is_admin:
            _show(users_button)
            _show(access_button)
            _hide(my_access_button)
        else:
            _hide(users_button)
            _hide(access_button)
            if logged_in:
                _show(my_access_button)
            else:
                _hide(my_access_button)

    def refresh_session() -> None:
        """Recalcula permisos y refresca la visibilidad de los botones."""
        refresh_permissions()
        refresh_session_ui()

    refresh_session_ui()
    for button, action in (
        (enroll_button, do_enroll),
        (login_button, do_login),
        (logout_button, do_logout),
        (users_button, do_users),
        (access_button, do_access),
        (my_access_button, do_my_access),
        (back_button, close),
    ):
        button.bind(menu_gui.EVENT_RETURN, _consume(action))
        button.bind(menu_gui.EVENT_SPACE, _consume(action))

    window.protocol(menu_gui.EVENT_CLOSE_WINDOW, close)
    window.bind(menu_gui.EVENT_ESCAPE, lambda _event: close())
    window.bind(menu_gui.EVENT_KEY_Q, lambda _event: close())
    window.bind(menu_gui.EVENT_KEY_Q_UPPER, lambda _event: close())

    try:
        # `wait_window` espera SOLO a que se destruya este Toplevel: con un
        # `mainloop()` anidado el bucle no termina al destruir la ventana
        # (la raiz del menu sigue viva, aunque este oculta) y el proceso queda
        # colgado sin interfaz.
        window.wait_window()
    except KeyboardInterrupt:
        logger.info("Interrumpido; volviendo al menu.")
    return 0
