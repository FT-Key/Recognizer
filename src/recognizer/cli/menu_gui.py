"""Menu grafico del launcher (imperative shell).

`tkinter` se importa solo dentro de `run_gui_menu` para que abrir el menu no
cargue cv2/MediaPipe/YOLO/torch. La logica pura (`build_menu_rows`) no toca
tkinter y es testeable sin display.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast

from recognizer.cli.menu import availability_label
from recognizer.core.config import AppsConfig
from recognizer.core.domain.app import AppAvailability, AppCatalog, AppId, AppRunRequest

if TYPE_CHECKING:
    import tkinter

LOGGER = logging.getLogger("recognizer.menu.gui")

GUI_WINDOW_TITLE = "Recognizer — menú"
GUI_OPEN_TEXT = "Abrir"
GUI_EXIT_TEXT = "Salir"
GUI_FRAME_PADDING = 12
GUI_LIST_MIN_HEIGHT = 4


class _Selectable(Protocol):
    """Listbox con seleccion tipada (typeshed deja `curselection` sin tipos)."""

    def curselection(self) -> tuple[int, ...]:
        """Indices seleccionados de la lista."""
        ...


@dataclass(frozen=True, slots=True)
class MenuRow:
    """Fila del menu grafico: app, estado legible y si se puede abrir."""

    number: int
    title: str
    label: str
    app_id: AppId | None
    selectable: bool


def build_menu_rows(catalog: AppCatalog, apps_config: AppsConfig) -> tuple[MenuRow, ...]:
    """Deriva las filas del menu grafico sin tocar tkinter (logica pura)."""
    rows: list[MenuRow] = []
    for number, info in enumerate(catalog.apps, start=1):
        availability = catalog.availability(info.app_id, enabled=apps_config.enabled)
        rows.append(
            MenuRow(
                number=number,
                title=info.title,
                label=availability_label(info, availability),
                app_id=info.app_id,
                selectable=availability is AppAvailability.AVAILABLE,
            )
        )
    return tuple(rows)


def run_gui_menu(
    *,
    request: AppRunRequest,
    apps_config: AppsConfig,
    catalog: AppCatalog | None = None,
    logger: logging.Logger = LOGGER,
    tk_factory: Callable[[], tkinter.Tk] | None = None,
) -> int:
    """Muestra el menu grafico y abre apps hasta que el usuario sale (0).

    La app elegida corre con la ventana oculta (`withdraw`) y al terminar se
    re-muestra (`deiconify`). Cerrar con la X, ESC o el boton Salir devuelve 0.
    `tk_factory` inyecta la clase Tk en tests (sin display real).
    """
    import tkinter
    from tkinter import ttk

    from recognizer.cli.menu import resolve_runner

    resolved_catalog = catalog if catalog is not None else AppCatalog()
    rows = build_menu_rows(resolved_catalog, apps_config)
    rows_by_number = {row.number: row for row in rows}

    tk_cls = tk_factory if tk_factory is not None else tkinter.Tk
    root = tk_cls()
    root.title(GUI_WINDOW_TITLE)

    frame = ttk.Frame(root, padding=GUI_FRAME_PADDING)
    frame.pack(fill="both", expand=True)

    listing = tkinter.Listbox(frame, height=max(len(rows), GUI_LIST_MIN_HEIGHT))
    for row in rows:
        listing.insert("end", f"{row.number}) {row.title} {row.label}")
    listing.pack(fill="both", expand=True)
    for index, row in enumerate(rows):
        if row.selectable:
            listing.selection_set(index)
            break

    def selected_row() -> MenuRow | None:
        picked = cast("_Selectable", listing).curselection()
        if not picked:
            return None
        return rows_by_number.get(picked[0] + 1)

    def open_selected() -> None:
        row = selected_row()
        if row is None:
            logger.info("Elige una aplicacion de la lista.")
            return
        if row.app_id is None or not row.selectable:
            logger.info("'%s' no esta disponible %s.", row.title, row.label)
            return
        runner = resolve_runner(row.app_id)
        if runner is None:
            logger.error("No hay runner para '%s'.", row.app_id.value)
            return
        logger.info("Abriendo '%s'... (ESC/q para volver al menu)", row.title)
        root.withdraw()
        try:
            runner(request)
        finally:
            root.deiconify()
        logger.info("Volviendo al menu principal.")

    def close() -> None:
        root.destroy()

    buttons = ttk.Frame(frame)
    buttons.pack(fill="x")
    open_button = ttk.Button(buttons, text=GUI_OPEN_TEXT, command=open_selected)
    open_button.pack(side="left")
    exit_button = ttk.Button(buttons, text=GUI_EXIT_TEXT, command=close)
    exit_button.pack(side="right")

    root.protocol("WM_DELETE_WINDOW", close)
    root.bind("<Escape>", lambda _event: close())
    root.bind("<Return>", lambda _event: open_selected())
    listing.bind("<Double-Button-1>", lambda _event: open_selected())

    try:
        root.mainloop()
    except KeyboardInterrupt:
        logger.info("Interrumpido; saliendo del menu.")
    return 0
