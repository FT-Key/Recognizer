"""Submenu grafico de reconocimiento facial (imperative shell) vintage.

Se abre desde el menu grafico cuando se elige ``FACE_AUTH``; la consola
(``run_face_auth`` en ``cli/apps/face_auth.py``) sigue como fallback con
``--no-gui``. ``tkinter`` y los runners de vision se importan dentro de las
funciones para no cargar modelos al abrir el menu.

El formulario de enrolamiento vive en ``face_enroll_gui`` y se abre con import
perezoso desde el boton ``Enrolar``; aqui solo queda la tarjeta de sesion y los
botones de accion.

Testabilidad (fakes necesarios)
------------------------------
Los tests inyectan ``tk_factory`` (fabrica del ``Toplevel``) y parchean
``tkinter.Frame/Label/Button/StringVar``:

- ``Toplevel`` (via ``tk_factory``): doble con ``title``, ``configure``,
  ``protocol``, ``bind``, ``withdraw``, ``deiconify``, ``destroy`` y
  ``wait_window``.
- ``Frame``/``Label``/``Button``: como en ``menu_gui`` (``Button`` registra
  su ``command`` y expone ``pack``/``pack_forget`` para alternar visibilidad).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING, Protocol

from recognizer.cli import menu_gui
from recognizer.cli.face_adapters import allowed_roles, store_is_empty
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.domain.identity import Identity, Role
from recognizer.core.ports.identity_provider import IdentityProvider

if TYPE_CHECKING:
    import tkinter

    from recognizer.cli.face_enroll_gui import EnrollRunner

LOGGER = logging.getLogger("recognizer.menu.face")

FACE_SUBMENU_TITLE = "Reconocimiento facial"
FACE_HEADER_TITLE = "RECONOCIMIENTO FACIAL"
FACE_HEADER_SUBTITLE = "enrola tu cara o inicia sesion"
FACE_SESSION_TEMPLATE = "Sesión: {name} ({role})"
FACE_GUEST_NAME = "invitado"
FACE_GUEST_ID = "sin sesión"
FACE_SESSION_DETAIL_TEMPLATE = "Rol: {role} · ID: {face_id}"
FACE_LOGIN_PROMPT = "Inicia sesión con tu rostro"
FACE_ENROLL_TEXT = "Enrolar"
FACE_LOGIN_TEXT = "Iniciar sesión"
FACE_LOGOUT_TEXT = "Cerrar sesión"
FACE_USERS_TEXT = "Usuarios"
FACE_ACCESS_TEXT = "Accesos"
FACE_MY_ACCESS_TEXT = "Mis accesos"
FACE_BACK_TEXT = "Volver"
FACE_FOOTER_HINT = "Enter: activar · ESC: volver"
FACE_UNKNOWN_ROLE = "?"
FACE_ENROLL_DENIED_TEMPLATE = "Enrolar sin permiso (tu rol: {role})."
FACE_ENROLL_LOG = "Abriendo formulario de enrolamiento... (ESC/q para volver)"
FACE_USERS_LOG = "Abriendo panel de usuarios... (ESC/q para volver)"
FACE_ACCESS_LOG = "Abriendo panel de accesos... (ESC/q para volver)"
FACE_SESSION_REFRESH_ERROR = "No se pudo refrescar la sesion visible (%s)."


class FaceActionRunner(Protocol):
    """Runner facial sin lector (login/logout)."""

    def __call__(self, request: AppRunRequest) -> int:
        """Ejecuta la accion; devuelve 0 si termino bien."""
        ...


def _default_provider(request: AppRunRequest, *, logger: logging.Logger) -> IdentityProvider:
    """Proveedor de sesion liviano (solo stdlib+json, sin modelos de vision)."""
    from recognizer.cli.face_adapters import default_identity_provider

    return default_identity_provider(request, logger=logger)


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


def _session_text(identity: Identity) -> str:
    """Linea unica de sesion para el header (nombre y rol reales).

    Para el invitado usa el nombre "invitado" pero el rol vigente de la
    identidad, de modo que el header y la tarjeta de sesion nunca difieran.
    """
    name = identity.name if identity.authenticated_at else FACE_GUEST_NAME
    return FACE_SESSION_TEMPLATE.format(name=name, role=identity.role.value)


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

    ``Enrolar`` abre el formulario ``run_enroll_form`` (import perezoso) con el
    runner inyectado. ``Login``/``Logout`` ocultan la ventana y corren su runner.
    ``Usuarios`` (admin) y ``Accesos``/``Mis accesos`` abren sus paneles tambien
    de forma perezosa. ``Volver``/X/ESC destruye la ventana y devuelve 0.
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
    state["is_first"] = store_is_empty(provider)
    state["allowed"] = allowed_roles(is_first=bool(state["is_first"]), role=current.role)

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
    session_label = tkinter.Label(
        header,
        text=_session_text(current),
        font=(body_family, theme.size_body_small, menu_gui.FONT_WEIGHT_BOLD),
        fg=theme.primary_contrast,
        bg=theme.primary,
        anchor=menu_gui.ANCHOR_WEST,
    )
    session_label.pack(fill=menu_gui.FILL_X)

    body = tkinter.Frame(window, bg=theme.surface)
    body.pack(
        side=menu_gui.SIDE_TOP,
        fill=menu_gui.FILL_BOTH,
        expand=True,
        padx=theme.pad_body,
        pady=theme.space_4,
    )

    # Tarjeta de sesion: nombre, rol e ID (o invitado) en una superficie elevada.
    session_card = tkinter.Frame(
        body,
        bg=theme.surface_alt,
        relief=menu_gui.RELIEF_RAISED,
        bd=menu_gui.BUTTON_BORDER_WIDTH,
    )
    session_card.pack(fill=menu_gui.FILL_X, pady=(menu_gui.BORDER_NONE, theme.space_3))
    session_name_label = tkinter.Label(
        session_card,
        text=FACE_GUEST_NAME,
        font=(body_family, theme.size_body, menu_gui.FONT_WEIGHT_BOLD),
        fg=theme.text,
        bg=theme.surface_alt,
        anchor=menu_gui.ANCHOR_WEST,
    )
    session_name_label.pack(
        fill=menu_gui.FILL_X, padx=theme.space_3, pady=(theme.space_2, menu_gui.BORDER_NONE)
    )
    session_role_label = tkinter.Label(
        session_card,
        text=FACE_SESSION_DETAIL_TEMPLATE.format(role=Role.VIEWER.value, face_id=FACE_GUEST_ID),
        font=(body_family, theme.size_body_small),
        fg=theme.text_muted,
        bg=theme.surface_alt,
        anchor=menu_gui.ANCHOR_WEST,
    )
    session_role_label.pack(fill=menu_gui.FILL_X, padx=theme.space_3)
    login_prompt_label = tkinter.Label(
        session_card,
        text=FACE_LOGIN_PROMPT,
        font=(body_family, theme.size_body),
        fg=theme.text,
        bg=theme.surface_alt,
        anchor=menu_gui.ANCHOR_WEST,
    )

    # Botones de accion agrupados; se muestran u ocultan segun sesion y rol.
    actions = tkinter.Frame(body, bg=theme.surface)
    actions.pack(fill=menu_gui.FILL_X)

    def _show(button: tkinter.Button) -> None:
        button.pack(side=menu_gui.SIDE_LEFT, padx=theme.space_1, pady=theme.space_1)

    def _hide(button: tkinter.Button) -> None:
        button.pack_forget()

    def close() -> None:
        window.destroy()

    def do_enroll() -> None:
        fresh_allowed = refresh_permissions()
        if not fresh_allowed:
            current_role = state["role"]
            role_name = current_role.value if isinstance(current_role, Role) else FACE_UNKNOWN_ROLE
            logger.warning(FACE_ENROLL_DENIED_TEMPLATE.format(role=role_name))
            return
        from recognizer.cli.face_enroll_gui import run_enroll_form

        runner = enroll_runner if enroll_runner is not None else _default_enroll_runner()
        logger.info(FACE_ENROLL_LOG)
        window.withdraw()
        try:
            run_enroll_form(
                replace(request),
                identity_provider=provider,
                enroll_runner=runner,
                logger=logger,
            )
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

    enroll_button = _make_button(actions, FACE_ENROLL_TEXT, do_enroll, primary=True)
    users_button = _make_button(actions, FACE_USERS_TEXT, do_users, primary=False)
    access_button = _make_button(actions, FACE_ACCESS_TEXT, do_access, primary=False)
    my_access_button = _make_button(actions, FACE_MY_ACCESS_TEXT, do_my_access, primary=False)
    logout_button = _make_button(actions, FACE_LOGOUT_TEXT, do_logout, primary=False)
    login_button = _make_button(session_card, FACE_LOGIN_TEXT, do_login, primary=True)

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
    back_button = _make_button(footer, FACE_BACK_TEXT, close, primary=False)
    back_button.pack(side=menu_gui.SIDE_RIGHT, padx=theme.pad_footer, pady=theme.pad_footer)

    def _render_session(identity: Identity) -> None:
        """Pinta la tarjeta de sesion y el boton de login segun haya login."""
        logged_in = bool(identity.authenticated_at)
        name = identity.name if logged_in else FACE_GUEST_NAME
        face_id = identity.face_id if logged_in else FACE_GUEST_ID
        try:
            session_name_label.configure(text=name)
            session_role_label.configure(
                text=FACE_SESSION_DETAIL_TEMPLATE.format(role=identity.role.value, face_id=face_id)
            )
            if logged_in:
                login_prompt_label.pack_forget()
                login_button.pack_forget()
            else:
                login_prompt_label.pack(
                    fill=menu_gui.FILL_X,
                    padx=theme.space_3,
                    pady=(theme.space_1, menu_gui.BORDER_NONE),
                )
                login_button.pack(fill=menu_gui.FILL_X, padx=theme.space_3, pady=theme.space_2)
        except Exception as exc:  # el refresco jamas tumba el submenu
            logger.debug(FACE_SESSION_REFRESH_ERROR, exc)

    def refresh_permissions() -> tuple[Role, ...]:
        """Relee la sesion y recalcula permisos; el gate usa datos frescos."""
        fresh = provider.refresh()
        fresh_first = store_is_empty(provider)
        fresh_allowed = allowed_roles(is_first=fresh_first, role=fresh.role)
        state["role"] = fresh.role
        state["name"] = fresh.name
        state["logged_in"] = bool(fresh.authenticated_at)
        state["is_admin"] = fresh.role is Role.ADMIN
        state["is_first"] = fresh_first
        state["allowed"] = fresh_allowed
        state["identity"] = fresh
        try:
            session_label.configure(text=_session_text(fresh))
        except Exception as exc:  # el refresco jamas tumba el submenu
            logger.debug(FACE_SESSION_REFRESH_ERROR, exc)
        return fresh_allowed

    def refresh_session_ui() -> None:
        """Muestra u oculta botones y tarjeta segun la sesion y el rol vigentes.

        Se crean siempre todos los botones y aqui se alterna su visibilidad con
        ``pack``/``pack_forget``: asi el usuario solo ve las acciones que puede
        hacer (Enrolar con permiso, Login sin sesion, Logout con sesion,
        Usuarios/Accesos solo admin, Mis accesos solo no-admin autenticado).
        """
        # Usa la misma identidad que calculo `refresh_permissions` (evita que el
        # header y la tarjeta de sesion muestren datos distintos).
        stored = state.get("identity")
        fresh = stored if isinstance(stored, Identity) else provider.current_identity()
        logged_in = bool(fresh.authenticated_at)
        is_admin = fresh.role is Role.ADMIN
        state["logged_in"] = logged_in
        state["is_admin"] = is_admin
        _render_session(fresh)
        raw_allowed = state["allowed"]
        allowed_now = raw_allowed if isinstance(raw_allowed, tuple) else ()
        if allowed_now:
            _show(enroll_button)
        else:
            _hide(enroll_button)
            logger.warning(FACE_ENROLL_DENIED_TEMPLATE.format(role=fresh.role.value))
        if logged_in:
            _show(logout_button)
        else:
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

    refresh_session()
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
