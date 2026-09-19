"""Panel de gestion de usuarios enrolados (imperative shell) vintage.

Solo admin: tabla de rostros con su foto de enrolamiento y acciones de editar
(nombre/rol), re-enrolar (captura 5 muestras nuevas) y eliminar. ``tkinter`` y
el runner de enrolamiento (que carga InsightFace) se importan dentro de las
funciones para mantener la carga perezosa.

Testabilidad: ``tk_factory`` inyecta el ``Toplevel`` y los tests parchean
``tkinter.Frame/Label/Button/Entry/OptionMenu/StringVar/PhotoImage`` y
``tkinter.ttk.Treeview``/``ttk.Scrollbar``. El repositorio y el proveedor de
identidad son inyectables; por defecto se construyen desde ``request``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING

from recognizer.cli import menu_gui
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.domain.face import EnrolledFace
from recognizer.core.domain.identity import Role
from recognizer.core.ports.face_repository import FaceRepository
from recognizer.core.ports.identity_provider import IdentityProvider

if TYPE_CHECKING:
    import tkinter

LOGGER = logging.getLogger("recognizer.menu.face.users")

USERS_PANEL_TITLE = "Usuarios enrolados"
USERS_HEADER_TITLE = "USUARIOS"
USERS_HEADER_SUBTITLE = "edita, re-enrola o elimina rostros"
USERS_TABLE_LABEL = "Rostros enrolados"
USERS_PREVIEW_LABEL = "Foto de enrolamiento"
USERS_PREVIEW_EMPTY = "sin foto"
USERS_EDIT_TEXT = "Editar"
USERS_REENROLL_TEXT = "Re-enrolar"
USERS_DELETE_TEXT = "Eliminar"
USERS_BACK_TEXT = "Volver"
USERS_SAVE_TEXT = "Guardar"
USERS_CANCEL_TEXT = "Cancelar"
USERS_NAME_LABEL = "Nombre"
USERS_ROLE_LABEL = "Rol"
USERS_EDIT_TITLE = "Editar rostro"
USERS_DELETE_TITLE = "Eliminar rostro"
USERS_FOOTER_HINT = "Selecciona una fila · ESC: volver"
USERS_NO_SELECTION = "Selecciona un rostro primero."
USERS_EMPTY_NAME = "El nombre no puede quedar vacio."
USERS_CONFIRM_DELETE = "¿Eliminar el rostro {name} ({face_id})?"
USERS_ADMIN_ONLY_TEMPLATE = "Panel de usuarios: se requiere rol admin (actual: {role})."
USERS_NO_STORE = "Sin almacen de rostros; panel de usuarios cancelado."
USERS_COLUMNS = ("id", "name", "role", "samples", "created")
USERS_COLUMN_HEADINGS = ("ID", "Nombre", "Rol", "Muestras", "Fecha")
USERS_COLUMN_WIDTHS = (90, 220, 100, 90, 220)
USERS_ROLE_CHOICES = (Role.ADMIN, Role.OPERATOR, Role.VIEWER)
USERS_PREVIEW_WIDTH = 40
USERS_PREVIEW_HEIGHT = 8


def run_users_panel(
    request: AppRunRequest,
    *,
    tk_factory: Callable[[], tkinter.Toplevel] | None = None,
    repository: FaceRepository | None = None,
    identity_provider: IdentityProvider | None = None,
    logger: logging.Logger = LOGGER,
) -> int:
    """Muestra el panel de usuarios (solo admin); devuelve 0 al cerrarlo.

    Con una identidad no admin no abre la ventana, avisa en el log y devuelve 1.
    ``repository``/``identity_provider`` se inyectan en tests; si faltan se
    construyen de forma perezosa desde ``request.config_path``.
    """
    import tkinter
    from tkinter import messagebox, ttk

    from recognizer.cli.face_adapters import default_face_repository, default_identity_provider

    theme = menu_gui.DEFAULT_THEME
    provider = (
        identity_provider
        if identity_provider is not None
        else default_identity_provider(request, logger=logger)
    )
    identity = provider.current_identity()
    if identity.role is not Role.ADMIN:
        logger.warning(USERS_ADMIN_ONLY_TEMPLATE.format(role=identity.role.value))
        return 1
    repo = repository if repository is not None else default_face_repository(request, logger=logger)
    if repo is None:
        logger.warning(USERS_NO_STORE)
        return 1

    tk_cls = tk_factory if tk_factory is not None else tkinter.Toplevel
    window = tk_cls()
    window.title(USERS_PANEL_TITLE)
    window.configure(bg=theme.surface)
    body_family = theme.font_body
    state: dict[str, object] = {"preview": None}

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
        text=USERS_HEADER_TITLE,
        font=(body_family, theme.size_display_small, menu_gui.FONT_WEIGHT_BOLD),
        fg=theme.primary_contrast,
        bg=theme.primary,
        anchor=menu_gui.ANCHOR_WEST,
    ).pack(fill=menu_gui.FILL_X)
    tkinter.Label(
        header,
        text=USERS_HEADER_SUBTITLE,
        font=(body_family, theme.size_body_small),
        fg=theme.primary_contrast,
        bg=theme.primary,
        anchor=menu_gui.ANCHOR_WEST,
    ).pack(fill=menu_gui.FILL_X)

    tkinter.Label(
        window,
        text=USERS_TABLE_LABEL,
        font=(body_family, theme.size_body, menu_gui.FONT_WEIGHT_BOLD),
        fg=theme.text,
        bg=theme.surface,
        anchor=menu_gui.ANCHOR_WEST,
    ).pack(fill=menu_gui.FILL_X, padx=theme.pad_body, pady=(theme.space_3, menu_gui.BORDER_NONE))

    table_frame = tkinter.Frame(window, bg=theme.surface)
    table_frame.pack(
        side=menu_gui.SIDE_TOP,
        fill=menu_gui.FILL_BOTH,
        expand=True,
        padx=theme.pad_body,
        pady=theme.space_2,
    )
    tree = ttk.Treeview(
        table_frame,
        columns=USERS_COLUMNS,
        show=menu_gui.TREE_SHOW_HEADINGS,
        selectmode=menu_gui.TREE_SELECT_BROWSE,
    )
    for key, heading, width in zip(
        USERS_COLUMNS, USERS_COLUMN_HEADINGS, USERS_COLUMN_WIDTHS, strict=True
    ):
        tree.heading(key, text=heading)
        tree.column(key, width=width, anchor=menu_gui.ANCHOR_WEST)
    scrollbar = ttk.Scrollbar(table_frame, orient=menu_gui.ORIENT_VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side=menu_gui.SIDE_RIGHT, fill=menu_gui.FILL_Y)
    tree.pack(side=menu_gui.SIDE_LEFT, fill=menu_gui.FILL_BOTH, expand=True)

    tkinter.Label(
        window,
        text=USERS_PREVIEW_LABEL,
        font=(body_family, theme.size_body_small, menu_gui.FONT_WEIGHT_BOLD),
        fg=theme.text,
        bg=theme.surface,
        anchor=menu_gui.ANCHOR_WEST,
    ).pack(fill=menu_gui.FILL_X, padx=theme.pad_body, pady=(theme.space_2, menu_gui.BORDER_NONE))
    preview_label = tkinter.Label(
        window,
        text=USERS_PREVIEW_EMPTY,
        font=(body_family, theme.size_body_small),
        fg=theme.text_muted,
        bg=theme.surface_sunken,
        width=USERS_PREVIEW_WIDTH,
        height=USERS_PREVIEW_HEIGHT,
        anchor=menu_gui.ANCHOR_WEST,
    )
    preview_label.pack(fill=menu_gui.FILL_X, padx=theme.pad_body, pady=theme.space_1)

    def _clear_preview() -> None:
        state["preview"] = None
        try:
            preview_label.configure(image="", text=USERS_PREVIEW_EMPTY)
        except Exception as exc:  # la vista previa nunca tumba el panel
            logger.debug("No se pudo limpiar la vista previa (%s).", exc)

    def _load_preview(face_id: str) -> None:
        path = repo.preview_path(face_id)
        if path is None:
            _clear_preview()
            return
        try:
            photo = tkinter.PhotoImage(file=str(path))
        except Exception as exc:  # sin foto o sin Tk: texto de respaldo
            logger.debug("Sin foto de %s (%s).", face_id, exc)
            _clear_preview()
            return
        state["preview"] = photo
        try:
            preview_label.configure(image=photo, text="")
        except Exception as exc:
            logger.debug("No se pudo mostrar la foto de %s (%s).", face_id, exc)

    def refresh_table() -> None:
        """Recarga la tabla desde el repositorio y limpia la seleccion."""
        for item in tree.get_children():
            tree.delete(item)
        for face in repo.list_all():
            tree.insert(
                "",
                "end",
                iid=face.face_id,
                values=(
                    face.face_id,
                    face.name,
                    face.role.value,
                    str(face.samples),
                    face.created_at,
                ),
            )
        _clear_preview()

    def _selected_face() -> EnrolledFace | None:
        selection = tree.selection()
        if not selection:
            logger.info(USERS_NO_SELECTION)
            return None
        face = repo.find_by_id(str(selection[0]))
        if face is None:
            logger.warning("El rostro %s ya no existe.", selection[0])
            refresh_table()
            return None
        return face

    def on_select(_event: tkinter.Event) -> None:
        selection = tree.selection()
        if not selection:
            _clear_preview()
            return
        _load_preview(str(selection[0]))

    def _open_edit_dialog(face: EnrolledFace) -> None:
        dialog = tk_cls()
        dialog.title(USERS_EDIT_TITLE)
        dialog.configure(bg=theme.surface)
        tkinter.Label(
            dialog,
            text=USERS_NAME_LABEL,
            font=(body_family, theme.size_body, menu_gui.FONT_WEIGHT_BOLD),
            fg=theme.text,
            bg=theme.surface,
            anchor=menu_gui.ANCHOR_WEST,
        ).pack(
            fill=menu_gui.FILL_X, padx=theme.pad_body, pady=(theme.space_2, menu_gui.BORDER_NONE)
        )
        name_entry = tkinter.Entry(dialog)
        name_entry.pack(fill=menu_gui.FILL_X, padx=theme.pad_body, pady=theme.space_1)
        try:
            name_entry.insert(0, face.name)
        except Exception as exc:  # fakes sin `insert`
            logger.debug("No se pudo precargar el nombre (%s).", exc)
        tkinter.Label(
            dialog,
            text=USERS_ROLE_LABEL,
            font=(body_family, theme.size_body, menu_gui.FONT_WEIGHT_BOLD),
            fg=theme.text,
            bg=theme.surface,
            anchor=menu_gui.ANCHOR_WEST,
        ).pack(
            fill=menu_gui.FILL_X, padx=theme.pad_body, pady=(theme.space_1, menu_gui.BORDER_NONE)
        )
        role_var = tkinter.StringVar()
        role_var.set(face.role.value)
        role_menu = tkinter.OptionMenu(
            dialog, role_var, *(role.value for role in USERS_ROLE_CHOICES)
        )
        # El __init__ de OptionMenu en typeshed no declara los kwargs del
        # Menubutton; se aplican con `configure`, que si los acepta.
        role_menu.configure(
            relief=menu_gui.RELIEF_RAISED,
            bd=menu_gui.BUTTON_BORDER_WIDTH,
            font=(body_family, theme.size_body, menu_gui.FONT_WEIGHT_BOLD),
            bg=theme.surface_alt,
            fg=theme.text,
            activebackground=theme.primary_soft,
            activeforeground=theme.text,
            cursor=menu_gui.CURSOR_HAND,
            anchor=menu_gui.ANCHOR_WEST,
        )
        role_menu.pack(fill=menu_gui.FILL_X, padx=theme.pad_body, pady=theme.space_1)

        def save() -> None:
            try:
                new_name = name_entry.get().strip()
            except Exception as exc:
                logger.warning("No se pudo leer el nombre (%s).", exc)
                return
            if not new_name:
                logger.warning(USERS_EMPTY_NAME)
                return
            try:
                new_role = Role(role_var.get().strip().lower())
            except ValueError:
                logger.warning("Rol no valido; se conserva %s.", face.role.value)
                new_role = face.role
            repo.update(replace(face, name=new_name, role=new_role))
            logger.info(
                "Rostro actualizado: %s (%s, rol %s).", new_name, face.face_id, new_role.value
            )
            dialog.destroy()
            refresh_table()

        buttons = tkinter.Frame(dialog, bg=theme.surface)
        buttons.pack(fill=menu_gui.FILL_X, padx=theme.pad_body, pady=theme.space_2)
        save_button = _make_button(buttons, USERS_SAVE_TEXT, save, primary=True)
        save_button.pack(side=menu_gui.SIDE_LEFT, padx=theme.space_1)
        cancel_button = _make_button(buttons, USERS_CANCEL_TEXT, dialog.destroy, primary=False)
        cancel_button.pack(side=menu_gui.SIDE_LEFT, padx=theme.space_1)

    def do_edit() -> None:
        face = _selected_face()
        if face is None:
            return
        _open_edit_dialog(face)

    def do_reenroll() -> None:
        face = _selected_face()
        if face is None:
            return
        from recognizer.cli.apps.face_auth import run_face_enroll

        logger.info("Re-enrolando %s (%s)... (ESC/q para volver)", face.name, face.face_id)
        window.withdraw()
        try:
            run_face_enroll(replace(request), face_id=face.face_id, reader=lambda _prompt: "")
        finally:
            window.deiconify()
        refresh_table()

    def do_delete() -> None:
        face = _selected_face()
        if face is None:
            return
        confirmed = messagebox.askyesno(
            USERS_DELETE_TITLE,
            USERS_CONFIRM_DELETE.format(name=face.name, face_id=face.face_id),
        )
        if not confirmed:
            return
        repo.delete(face.face_id)
        logger.info("Rostro eliminado: %s (%s).", face.name, face.face_id)
        refresh_table()

    def close() -> None:
        window.destroy()

    actions = tkinter.Frame(window, bg=theme.surface)
    actions.pack(fill=menu_gui.FILL_X, padx=theme.pad_body, pady=theme.space_2)
    edit_button = _make_button(actions, USERS_EDIT_TEXT, do_edit, primary=False)
    edit_button.pack(side=menu_gui.SIDE_LEFT, padx=theme.space_1)
    reenroll_button = _make_button(actions, USERS_REENROLL_TEXT, do_reenroll, primary=False)
    reenroll_button.pack(side=menu_gui.SIDE_LEFT, padx=theme.space_1)
    delete_button = _make_button(actions, USERS_DELETE_TEXT, do_delete, primary=False)
    delete_button.pack(side=menu_gui.SIDE_LEFT, padx=theme.space_1)

    footer = tkinter.Frame(window, bg=theme.surface_alt)
    footer.pack(side=menu_gui.SIDE_BOTTOM, fill=menu_gui.FILL_X)
    tkinter.Label(
        footer,
        text=USERS_FOOTER_HINT,
        font=(body_family, theme.size_body_small),
        fg=theme.text_muted,
        bg=theme.surface_alt,
        anchor=menu_gui.ANCHOR_WEST,
    ).pack(side=menu_gui.SIDE_LEFT, padx=theme.pad_footer, pady=theme.pad_footer)
    back_button = _make_button(footer, USERS_BACK_TEXT, close, primary=False)
    back_button.pack(side=menu_gui.SIDE_RIGHT, padx=theme.pad_footer, pady=theme.pad_footer)

    tree.bind(menu_gui.EVENT_TREE_SELECT, on_select)
    for button, action in (
        (edit_button, do_edit),
        (reenroll_button, do_reenroll),
        (delete_button, do_delete),
        (back_button, close),
    ):
        button.bind(menu_gui.EVENT_RETURN, _consume(action))
        button.bind(menu_gui.EVENT_SPACE, _consume(action))

    window.protocol(menu_gui.EVENT_CLOSE_WINDOW, close)
    window.bind(menu_gui.EVENT_ESCAPE, lambda _event: close())
    window.bind(menu_gui.EVENT_KEY_Q, lambda _event: close())
    window.bind(menu_gui.EVENT_KEY_Q_UPPER, lambda _event: close())

    refresh_table()
    try:
        window.wait_window()
    except KeyboardInterrupt:
        logger.info("Interrumpido; volviendo al submenu.")
    return 0
