"""Panel de accesos faciales (imperative shell) vintage.

Admin ve todos los logins con su foto; un usuario autenticado no admin ve solo
sus propios accesos y **sin** foto. Viewer/anónimo no debería llegar aquí. Por
seguridad, el panel fuerza el filtrado y la ausencia de fotos cuando la
identidad no es admin, aunque el llamador pida lo contrario.

``tkinter`` se importa dentro de la función; el registro de accesos y la
identidad son inyectables (por defecto se construyen desde ``request``).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from recognizer.cli import menu_gui
from recognizer.core.domain.access import AccessEvent
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.domain.identity import Identity, Role
from recognizer.core.ports.access_log import AccessLogRepository

if TYPE_CHECKING:
    import tkinter

LOGGER = logging.getLogger("recognizer.menu.face.access")

ACCESS_PANEL_TITLE = "Registro de accesos"
ACCESS_HEADER_TITLE = "ACCESOS"
ACCESS_HEADER_SUBTITLE = "logins faciales registrados"
ACCESS_MY_HEADER_SUBTITLE = "tus logins faciales"
ACCESS_TABLE_LABEL = "Historial"
ACCESS_PHOTO_LABEL = "Foto del login"
ACCESS_PHOTO_EMPTY = "sin foto"
ACCESS_BACK_TEXT = "Volver"
ACCESS_FOOTER_HINT = "Selecciona una fila · ESC: volver"
ACCESS_NO_STORE = "Sin registro de accesos; panel cancelado."
ACCESS_COLUMNS = ("timestamp", "name", "id", "role")
ACCESS_COLUMN_HEADINGS = ("Fecha", "Nombre", "ID", "Rol")
ACCESS_COLUMN_WIDTHS = (220, 200, 90, 100)
ACCESS_PHOTO_WIDTH = 40
ACCESS_PHOTO_HEIGHT = 8


def run_access_panel(
    request: AppRunRequest,
    *,
    tk_factory: Callable[[], tkinter.Toplevel] | None = None,
    repository: AccessLogRepository | None = None,
    identity: Identity | None = None,
    show_photos: bool = True,
    logger: logging.Logger = LOGGER,
) -> int:
    """Muestra el historial de accesos; devuelve 0 al cerrarlo.

    Con identidad admin se listan todos los eventos y se muestran sus fotos
    (si ``show_photos``). Con identidad no admin se fuerzan ``show_photos=False``
    y el filtro por ``identity.face_id``, aunque el llamador pida otra cosa.
    ``repository``/``identity`` se inyectan en tests.
    """
    import tkinter
    from tkinter import ttk

    from recognizer.cli.face_adapters import default_access_repository, default_identity_provider

    theme = menu_gui.DEFAULT_THEME
    current = identity
    if current is None:
        current = default_identity_provider(request, logger=logger).current_identity()
    is_admin = current.role is Role.ADMIN
    if not is_admin:
        show_photos = False
    repo = (
        repository if repository is not None else default_access_repository(request, logger=logger)
    )
    if repo is None:
        logger.warning(ACCESS_NO_STORE)
        return 1
    events = repo.list_all() if is_admin else repo.find_by_face(current.face_id)

    tk_cls = tk_factory if tk_factory is not None else tkinter.Toplevel
    window = tk_cls()
    window.title(ACCESS_PANEL_TITLE)
    window.configure(bg=theme.surface)
    body_family = theme.font_body
    state: dict[str, object] = {"photo": None}
    rows: list[AccessEvent] = list(events)

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
        text=ACCESS_HEADER_TITLE,
        font=(body_family, theme.size_display_small, menu_gui.FONT_WEIGHT_BOLD),
        fg=theme.primary_contrast,
        bg=theme.primary,
        anchor=menu_gui.ANCHOR_WEST,
    ).pack(fill=menu_gui.FILL_X)
    tkinter.Label(
        header,
        text=ACCESS_HEADER_SUBTITLE if is_admin else ACCESS_MY_HEADER_SUBTITLE,
        font=(body_family, theme.size_body_small),
        fg=theme.primary_contrast,
        bg=theme.primary,
        anchor=menu_gui.ANCHOR_WEST,
    ).pack(fill=menu_gui.FILL_X)

    tkinter.Label(
        window,
        text=ACCESS_TABLE_LABEL,
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
        columns=ACCESS_COLUMNS,
        show=menu_gui.TREE_SHOW_HEADINGS,
        selectmode=menu_gui.TREE_SELECT_BROWSE,
    )
    for key, heading, width in zip(
        ACCESS_COLUMNS, ACCESS_COLUMN_HEADINGS, ACCESS_COLUMN_WIDTHS, strict=True
    ):
        tree.heading(key, text=heading)
        tree.column(key, width=width, anchor=menu_gui.ANCHOR_WEST)
    scrollbar = ttk.Scrollbar(table_frame, orient=menu_gui.ORIENT_VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side=menu_gui.SIDE_RIGHT, fill=menu_gui.FILL_Y)
    tree.pack(side=menu_gui.SIDE_LEFT, fill=menu_gui.FILL_BOTH, expand=True)

    photo_label: tkinter.Label | None = None
    if show_photos:
        tkinter.Label(
            window,
            text=ACCESS_PHOTO_LABEL,
            font=(body_family, theme.size_body_small, menu_gui.FONT_WEIGHT_BOLD),
            fg=theme.text,
            bg=theme.surface,
            anchor=menu_gui.ANCHOR_WEST,
        ).pack(
            fill=menu_gui.FILL_X, padx=theme.pad_body, pady=(theme.space_2, menu_gui.BORDER_NONE)
        )
        photo_label = tkinter.Label(
            window,
            text=ACCESS_PHOTO_EMPTY,
            font=(body_family, theme.size_body_small),
            fg=theme.text_muted,
            bg=theme.surface_sunken,
            width=ACCESS_PHOTO_WIDTH,
            height=ACCESS_PHOTO_HEIGHT,
            anchor=menu_gui.ANCHOR_WEST,
        )
        photo_label.pack(fill=menu_gui.FILL_X, padx=theme.pad_body, pady=theme.space_1)

    def _clear_photo() -> None:
        state["photo"] = None
        if photo_label is None:
            return
        try:
            photo_label.configure(image="", text=ACCESS_PHOTO_EMPTY)
        except Exception as exc:
            logger.debug("No se pudo limpiar la foto del acceso (%s).", exc)

    def _load_photo(path: Path) -> None:
        if photo_label is None:
            return
        try:
            photo = tkinter.PhotoImage(file=str(path))
        except Exception as exc:  # sin foto o sin Tk: texto de respaldo
            logger.debug("Sin foto del acceso %s (%s).", path, exc)
            _clear_photo()
            return
        state["photo"] = photo
        try:
            photo_label.configure(image=photo, text="")
        except Exception as exc:
            logger.debug("No se pudo mostrar la foto del acceso (%s).", exc)

    def _event_by_iid(iid: str) -> AccessEvent | None:
        try:
            index = int(iid)
        except ValueError:
            return None
        if 0 <= index < len(rows):
            return rows[index]
        return None

    def on_select(_event: tkinter.Event) -> None:
        if not show_photos:
            return
        selection = tree.selection()
        if not selection:
            _clear_photo()
            return
        access = _event_by_iid(str(selection[0]))
        if access is None:
            _clear_photo()
            return
        path = repo.image_path(access)
        if path is None:
            _clear_photo()
            return
        _load_photo(path)

    for index, access in enumerate(rows):
        tree.insert(
            "",
            "end",
            iid=str(index),
            values=(access.timestamp, access.name, access.face_id, access.role.value),
        )

    def close() -> None:
        window.destroy()

    footer = tkinter.Frame(window, bg=theme.surface_alt)
    footer.pack(side=menu_gui.SIDE_BOTTOM, fill=menu_gui.FILL_X)
    tkinter.Label(
        footer,
        text=ACCESS_FOOTER_HINT,
        font=(body_family, theme.size_body_small),
        fg=theme.text_muted,
        bg=theme.surface_alt,
        anchor=menu_gui.ANCHOR_WEST,
    ).pack(side=menu_gui.SIDE_LEFT, padx=theme.pad_footer, pady=theme.pad_footer)
    back_button = _make_button(footer, ACCESS_BACK_TEXT, close, primary=False)
    back_button.pack(side=menu_gui.SIDE_RIGHT, padx=theme.pad_footer, pady=theme.pad_footer)

    tree.bind(menu_gui.EVENT_TREE_SELECT, on_select)
    back_button.bind(menu_gui.EVENT_RETURN, _consume(close))
    back_button.bind(menu_gui.EVENT_SPACE, _consume(close))

    window.protocol(menu_gui.EVENT_CLOSE_WINDOW, close)
    window.bind(menu_gui.EVENT_ESCAPE, lambda _event: close())
    window.bind(menu_gui.EVENT_KEY_Q, lambda _event: close())
    window.bind(menu_gui.EVENT_KEY_Q_UPPER, lambda _event: close())

    try:
        window.wait_window()
    except KeyboardInterrupt:
        logger.info("Interrumpido; volviendo al submenu.")
    return 0
