"""Menu grafico del launcher (imperative shell) con estetica Vintage.

`tkinter` se importa dentro de las funciones para que abrir el menu no cargue
cv2/MediaPipe/YOLO/torch. La logica pura (`build_menu_rows`) no toca tkinter.

Testabilidad (fakes necesarios)
-------------------------------
Los tests inyectan `tk_factory` y sustituyen atributos del modulo `tkinter`
justo antes de llamar a `run_gui_menu`; como los widgets se resuelven como
`tkinter.Frame`/`tkinter.Label`/`tkinter.Button`/`tkinter.PhotoImage` en tiempo
de llamada, basta con parchear esos nombres:

- `tkinter.Frame`, `tkinter.Label`, `tkinter.Button`, `tkinter.PhotoImage`:
  dobles que acepten los kwargs usados y expongan `pack`, `bind`, `focus_set`
  y `configure` (los `Button` registran su `command`).
- `tkinter.Canvas` y `tkinter.Scrollbar` (lista desplazable): dobles con
  `pack`, `configure`, `create_window`, `bbox`, `itemconfigure` y `yview`/`set`.
- `Tk` (via `tk_factory`): doble con `title`, `configure`, `geometry`,
  `minsize`, `resizable`, `winfo_screenwidth`, `winfo_screenheight`,
  `protocol`, `bind`, `withdraw`, `deiconify`, `destroy` y `mainloop`.

El branding (`_apply_branding`) falla en silencio: si `ctypes`, `PhotoImage` o
los assets no estan, el menu sigue sin icono ni fuente pixel. Retiene las
referencias del logo y del icono (anti-GC) en `_Branding`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import partial
from typing import TYPE_CHECKING, Final

from recognizer.cli.menu import LABEL_NO_PERMISSION, availability_label
from recognizer.cli.paths import desktop_icon_path, desktop_logo_path, display_font_paths
from recognizer.core.config import AppsConfig
from recognizer.core.domain.app import AppAvailability, AppCatalog, AppId, AppRunRequest
from recognizer.core.domain.camera import CameraInfo
from recognizer.core.domain.identity import (
    AllowAllPolicy,
    AppPolicy,
    Identity,
    anonymous_identity,
)
from recognizer.core.ports.camera_discovery import CameraEnumerator
from recognizer.core.ports.identity_provider import IdentityProvider

if TYPE_CHECKING:
    import tkinter

LOGGER = logging.getLogger("recognizer.menu.gui")

# --- Textos -----------------------------------------------------------------
GUI_WINDOW_TITLE = "Recognizer"
GUI_OPEN_TEXT = "Abrir"
GUI_EXIT_TEXT = "Salir"
GUI_HEADER_TITLE = "R E C O G N I Z E R"
GUI_HEADER_SUBTITLE = "control por camara · elige una aplicacion"
GUI_APPS_SECTION = "APLICACIONES"
GUI_FOOTER_HINT = "Enter: abrir · ESC: salir"
BUTTON_TEXT_TEMPLATE = "{number}. {title}\n{description}"
GUI_CAMERA_LABEL = "Cámara"
GUI_CAMERA_DETECT_TEXT = "Detectar"
GUI_CAMERA_AUTO_TEXT = "auto"
GUI_CAMERA_LOG_TEMPLATE = "Camaras detectadas: {count}."

# --- Geometria --------------------------------------------------------------
WINDOW_WIDTH = 760
WINDOW_MIN_WIDTH = 520
WINDOW_MIN_HEIGHT = 420
# La ventana se limita al 90% del alto de pantalla para dejar margen al SO.
WINDOW_SCREEN_HEIGHT_RATIO = 0.9
# Deja la ventana a un tercio de la parte superior de la pantalla.
WINDOW_TOP_DIVISOR = 3
# Altura de linea aproximada = tamano de fuente * factor (incluye interlineado).
FONT_LINE_HEIGHT_FACTOR = 1.7
# La descripcion de cada app puede envolver hasta 2 lineas antes de recortarse.
DESCRIPTION_MAX_LINES = 2
# Ancho minimo de envoltura (px) para el texto del boton de cada app.
WRAPLENGTH_MIN = 200
# Tamano del logo de cabecera (`minilogo-128.png`) y ancho reservado al badge.
HEADER_LOGO_SIZE = 128
BADGE_WIDTH_ESTIMATE = 140
BUTTON_BORDER_WIDTH = 3
BADGE_BORDER_WIDTH = 1
FOCUS_HIGHLIGHT_WIDTH = 2
BORDER_NONE = 0
PAD_BUTTON_X = 16
PAD_BUTTON_Y = 10
PAD_BADGE_X = 8
PAD_BADGE_Y = 4
PAD_ROW = 4
PAD_HEADER = 16
PAD_FOOTER = 8
PAD_BODY = 24

# --- Tokens de color (tema claro, espejo de web/src/styles/theme.css) --------
COLOR_PRIMARY = "#008080"
COLOR_PRIMARY_STRONG = "#006666"
COLOR_PRIMARY_SOFT = "#99cccc"
COLOR_PRIMARY_CONTRAST = "#ffffff"
COLOR_SURFACE = "#c0c0c0"
COLOR_SURFACE_ALT = "#d4d0c8"
COLOR_SURFACE_SUNKEN = "#b0aca4"
COLOR_TEXT = "#000000"
COLOR_TEXT_MUTED = "#3a3a3a"
COLOR_SUCCESS = "#16a34a"
COLOR_WARNING = "#d97706"
COLOR_DANGER = "#dc2626"
COLOR_NEUTRAL = "#808080"
COLOR_BEVEL_LIGHT = "#ffffff"
COLOR_BEVEL_DARK = "#808080"

# --- Tokens de espaciado (escala 4/8/12/16/24/32) ---------------------------
SPACE_1 = 4
SPACE_2 = 8
SPACE_3 = 12
SPACE_4 = 16
SPACE_6 = 24
SPACE_8 = 32

# --- Tokens de tipografia ---------------------------------------------------
FONT_DISPLAY_FAMILY = "Silkscreen"
FONT_DISPLAY_FALLBACK = "Courier New"
FONT_BODY = "Consolas"
FONT_BODY_FALLBACK = "Courier New"
FONT_SIZE_DISPLAY = 20
FONT_SIZE_DISPLAY_SMALL = 9
FONT_SIZE_BODY = 11
FONT_SIZE_BODY_SMALL = 9
FONT_SIZE_BADGE = 8
FONT_WEIGHT_BOLD = "bold"

# --- Literales de la API de Tk ----------------------------------------------
FR_PRIVATE: Final = 0x10
ANCHOR_WEST: Final = "w"
JUSTIFY_LEFT: Final = "left"
RELIEF_RAISED: Final = "raised"
STATE_NORMAL: Final = "normal"
STATE_DISABLED: Final = "disabled"
CURSOR_HAND: Final = "hand2"
CURSOR_ARROW: Final = "arrow"
SIDE_LEFT: Final = "left"
SIDE_RIGHT: Final = "right"
SIDE_TOP: Final = "top"
SIDE_BOTTOM: Final = "bottom"
FILL_X: Final = "x"
FILL_Y: Final = "y"
FILL_BOTH: Final = "both"
ORIENT_VERTICAL: Final = "vertical"
ANCHOR_NORTH_WEST: Final = "nw"
EVENT_CONFIGURE: Final = "<Configure>"
EVENT_CLOSE_WINDOW: Final = "WM_DELETE_WINDOW"
EVENT_ESCAPE: Final = "<Escape>"
EVENT_KEY_Q: Final = "<q>"
EVENT_KEY_Q_UPPER: Final = "<Q>"
EVENT_RETURN: Final = "<Return>"
EVENT_SPACE: Final = "<space>"
EVENT_UP: Final = "<Up>"
EVENT_DOWN: Final = "<Down>"
EVENT_DOUBLE_CLICK: Final = "<Double-Button-1>"
EVENT_MOUSEWHEEL: Final = "<MouseWheel>"
SCROLL_UNITS: Final = "units"
WHEEL_DELTA: Final = 120
TK_BREAK: Final = "break"
TK_ALL: Final = "all"


@dataclass(frozen=True, slots=True)
class MenuTheme:
    """Tokens visuales del menu: unica fuente de verdad de colores y medidas."""

    primary: str
    primary_strong: str
    primary_soft: str
    primary_contrast: str
    surface: str
    surface_alt: str
    surface_sunken: str
    text: str
    text_muted: str
    success: str
    warning: str
    danger: str
    neutral: str
    bevel_light: str
    bevel_dark: str
    space_1: int
    space_2: int
    space_3: int
    space_4: int
    space_6: int
    space_8: int
    pad_button_x: int
    pad_button_y: int
    pad_badge_x: int
    pad_badge_y: int
    pad_row: int
    pad_header: int
    pad_footer: int
    pad_body: int
    font_body: str
    font_body_fallback: str
    font_display_fallback: str
    size_display: int
    size_display_small: int
    size_body: int
    size_body_small: int
    size_badge: int


DEFAULT_THEME = MenuTheme(
    primary=COLOR_PRIMARY,
    primary_strong=COLOR_PRIMARY_STRONG,
    primary_soft=COLOR_PRIMARY_SOFT,
    primary_contrast=COLOR_PRIMARY_CONTRAST,
    surface=COLOR_SURFACE,
    surface_alt=COLOR_SURFACE_ALT,
    surface_sunken=COLOR_SURFACE_SUNKEN,
    text=COLOR_TEXT,
    text_muted=COLOR_TEXT_MUTED,
    success=COLOR_SUCCESS,
    warning=COLOR_WARNING,
    danger=COLOR_DANGER,
    neutral=COLOR_NEUTRAL,
    bevel_light=COLOR_BEVEL_LIGHT,
    bevel_dark=COLOR_BEVEL_DARK,
    space_1=SPACE_1,
    space_2=SPACE_2,
    space_3=SPACE_3,
    space_4=SPACE_4,
    space_6=SPACE_6,
    space_8=SPACE_8,
    pad_button_x=PAD_BUTTON_X,
    pad_button_y=PAD_BUTTON_Y,
    pad_badge_x=PAD_BADGE_X,
    pad_badge_y=PAD_BADGE_Y,
    pad_row=PAD_ROW,
    pad_header=PAD_HEADER,
    pad_footer=PAD_FOOTER,
    pad_body=PAD_BODY,
    font_body=FONT_BODY,
    font_body_fallback=FONT_BODY_FALLBACK,
    font_display_fallback=FONT_DISPLAY_FALLBACK,
    size_display=FONT_SIZE_DISPLAY,
    size_display_small=FONT_SIZE_DISPLAY_SMALL,
    size_body=FONT_SIZE_BODY,
    size_body_small=FONT_SIZE_BODY_SMALL,
    size_badge=FONT_SIZE_BADGE,
)


@dataclass(frozen=True, slots=True)
class MenuRow:
    """Fila del menu grafico: app, estado legible y si se puede abrir."""

    number: int
    title: str
    label: str
    app_id: AppId | None
    selectable: bool
    description: str = ""
    availability: AppAvailability = AppAvailability.AVAILABLE
    denied: bool = False


@dataclass(frozen=True, slots=True)
class _Branding:
    """Resultado del branding: familia display y referencias anti-GC."""

    display_family: str
    logo: tkinter.PhotoImage | None
    icon: tkinter.PhotoImage | None


def build_menu_rows(
    catalog: AppCatalog,
    apps_config: AppsConfig,
    *,
    identity: Identity | None = None,
    policy: AppPolicy | None = None,
) -> tuple[MenuRow, ...]:
    """Deriva las filas del menu grafico sin tocar tkinter (logica pura).

    Con ``identity`` y ``policy`` las apps disponibles pero no permitidas se
    marcan con ``[sin permiso]`` y no son seleccionables; sin ambas, las filas
    son las historicas (sin filtro).
    """
    rows: list[MenuRow] = []
    current = identity if identity is not None else anonymous_identity()
    for number, info in enumerate(catalog.apps, start=1):
        availability = catalog.availability(info.app_id, enabled=apps_config.enabled)
        label = availability_label(info, availability)
        denied = (
            policy is not None
            and availability is AppAvailability.AVAILABLE
            and not policy.can_launch(current, app_id=info.app_id)
        )
        if denied:
            label = f"{label} {LABEL_NO_PERMISSION}"
        rows.append(
            MenuRow(
                number=number,
                title=info.title,
                label=label,
                app_id=info.app_id,
                selectable=availability is AppAvailability.AVAILABLE and not denied,
                description=info.description,
                availability=availability,
                denied=denied,
            )
        )
    return tuple(rows)


def _line_height(font_size: int) -> int:
    """Alto aproximado en pixeles de una linea de texto para `font_size`."""
    return round(font_size * FONT_LINE_HEIGHT_FACTOR)


def _row_height() -> int:
    """Alto estimado de una fila de app: titulo + descripcion envuelta + chrome."""
    text_lines = 1 + DESCRIPTION_MAX_LINES
    chrome = 2 * (PAD_BUTTON_Y + BUTTON_BORDER_WIDTH + PAD_ROW)
    return text_lines * _line_height(FONT_SIZE_BODY) + chrome


def _header_height() -> int:
    """Alto estimado de la cabecera: el mayor entre logo y bloque de titulos."""
    logo = HEADER_LOGO_SIZE + 2 * SPACE_3
    titles = _line_height(FONT_SIZE_DISPLAY) + _line_height(FONT_SIZE_BODY_SMALL) + 2 * SPACE_3
    return max(logo, titles)


def _footer_height() -> int:
    """Alto estimado del pie: botones Abrir/Salir mas su padding."""
    button = _line_height(FONT_SIZE_BODY) + 2 * (SPACE_1 + BUTTON_BORDER_WIDTH)
    return button + 2 * PAD_FOOTER


def _window_height(row_count: int) -> int:
    """Alto necesario para mostrar `row_count` filas (sin limite de pantalla)."""
    body = 2 * SPACE_4 + _line_height(FONT_SIZE_DISPLAY_SMALL) + SPACE_2
    return _header_height() + body + row_count * _row_height() + _footer_height()


def compute_window_geometry(
    row_count: int, screen_width: int, screen_height: int
) -> tuple[int, int, int, int]:
    """Calcula (ancho, alto, x, y) de la ventana sin tocar tkinter (pura).

    El ancho se limita al de la pantalla (`min(WINDOW_WIDTH, screen_width)`).
    El alto crece con el numero de filas, respeta `WINDOW_MIN_HEIGHT` y se
    limita al 90% de la pantalla; la lista es desplazable si el contenido
    excede ese tope, de modo que todas las filas siguen siendo accesibles.
    """
    width = min(WINDOW_WIDTH, screen_width)
    content_height = max(_window_height(row_count), WINDOW_MIN_HEIGHT)
    max_height = max(WINDOW_MIN_HEIGHT, round(screen_height * WINDOW_SCREEN_HEIGHT_RATIO))
    height = min(content_height, max_height)
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // WINDOW_TOP_DIVISOR)
    return width, height, x, y


def _button_wraplength(window_width: int = WINDOW_WIDTH) -> int:
    """Ancho util (px) para envolver el texto del boton de cada app."""
    chrome = 2 * (PAD_BODY + SPACE_2 + BUTTON_BORDER_WIDTH + PAD_BUTTON_X)
    return max(WRAPLENGTH_MIN, window_width - chrome - BADGE_WIDTH_ESTIMATE)


def _badge_background(availability: AppAvailability, theme: MenuTheme) -> str:
    """Color de fondo del badge segun el estado de la app (contraste AA)."""
    match availability:
        case AppAvailability.AVAILABLE:
            return theme.primary
        case AppAvailability.DISABLED:
            return theme.neutral
        case AppAvailability.COMING_SOON:
            return theme.warning
        case _:
            return theme.neutral


def badge_foreground(availability: AppAvailability, theme: MenuTheme) -> str:
    """Color de texto del badge, con contraste AA (>= 4.5:1) sobre su fondo.

    AVAILABLE: blanco sobre teal ``#008080`` = 4.77:1 (pasa).
    DISABLED/COMING_SOON/otros: negro sobre gris ``#808080`` = 5.3:1 y sobre
    ambar ``#d97706`` = 6.6:1; el blanco fallaba (3.95:1 y 3.19:1).
    """
    match availability:
        case AppAvailability.AVAILABLE:
            return theme.primary_contrast
        case _:
            return theme.text


def _event_handler(
    action: Callable[[], None], *, consume: bool
) -> Callable[[tkinter.Event], str | None]:
    """Adapta una accion sin argumentos a un manejador de evento de Tk.

    Con ``consume=True`` devuelve ``TK_BREAK`` para que el binding nativo del
    boton (Enter/espacio) no vuelva a disparar la misma accion.
    """

    def handler(_event: tkinter.Event) -> str | None:
        action()
        return TK_BREAK if consume else None

    return handler


def _scroll_canvas(canvas: tkinter.Canvas, event: tkinter.Event) -> str:
    """Desplaza la lista con la rueda del raton aunque el puntero este sobre un boton.

    El evento se enlaza en la raiz (`Tk`), que forma parte de los `bindtags` de
    todos sus descendientes, de modo que la rueda funciona sobre cualquier widget
    de la lista y no solo sobre la barra de desplazamiento.
    """
    delta = getattr(event, "delta", 0)
    if delta == 0:
        return TK_BREAK
    steps = max(1, abs(delta) // WHEEL_DELTA)
    canvas.yview_scroll(-steps if delta > 0 else steps, SCROLL_UNITS)
    return TK_BREAK


def _register_display_font(*, logger: logging.Logger) -> str:
    """Registra la fuente pixel en Windows; devuelve la familia a usar."""
    import ctypes

    font_paths = display_font_paths()
    if not font_paths:
        return FONT_DISPLAY_FALLBACK
    try:
        for font_path in font_paths:
            ctypes.windll.gdi32.AddFontResourceExW(str(font_path), FR_PRIVATE, 0)
    except (OSError, AttributeError) as exc:
        logger.debug("No se pudo registrar la fuente pixel (%s).", exc)
        return FONT_DISPLAY_FALLBACK
    return FONT_DISPLAY_FAMILY


def _apply_window_icon(root: tkinter.Tk, *, logger: logging.Logger) -> tkinter.PhotoImage | None:
    """Pone el icono de la ventana (.ico y si no PNG); nunca lanza.

    Devuelve el `PhotoImage` del icono para que el llamador retenga la
    referencia: si se descarta, el recolector lo libera y Tk pierde el icono.
    """
    import tkinter

    icon_path = desktop_icon_path()
    if icon_path is not None:
        try:
            root.iconbitmap(str(icon_path))  # type: ignore[no-untyped-call]
            return None
        except Exception as exc:  # el icono jamas debe tumbar el menu
            logger.debug("iconbitmap no disponible (%s); se prueba iconphoto.", exc)
    logo_path = desktop_logo_path()
    if logo_path is None:
        return None
    try:
        photo = tkinter.PhotoImage(file=str(logo_path))
        root.iconphoto(True, photo)
    except Exception as exc:  # idem: cualquier fallo del icono es no fatal
        logger.debug("Sin icono de ventana: %s", exc)
        return None
    return photo


def _load_logo(*, logger: logging.Logger) -> tkinter.PhotoImage | None:
    """Carga el logo de cabecera; ``None`` si no hay asset o falla Tk."""
    import tkinter

    logo_path = desktop_logo_path()
    if logo_path is None:
        return None
    try:
        return tkinter.PhotoImage(file=str(logo_path))
    except Exception as exc:  # tolerante a fallos: el menu funciona sin logo
        logger.debug("No se pudo cargar el logo de cabecera (%s).", exc)
        return None


def _resolve_body_font(root: tkinter.Tk, *, logger: logging.Logger) -> str:
    """Familia del cuerpo: Consolas si esta instalada, si no Courier New."""
    from tkinter import font as tkfont

    try:
        families = set(tkfont.families(root))
    except Exception as exc:  # sin display o con fakes no hay lista de fuentes
        logger.debug("No se pudieron listar las fuentes (%s).", exc)
        return FONT_BODY_FALLBACK
    return FONT_BODY if FONT_BODY in families else FONT_BODY_FALLBACK


def _apply_branding(root: tkinter.Tk, *, logger: logging.Logger) -> _Branding:
    """Aplica fuente, icono y logo; devuelve las referencias a conservar."""
    display_family = _register_display_font(logger=logger)
    icon = _apply_window_icon(root, logger=logger)
    logo = _load_logo(logger=logger)
    return _Branding(display_family=display_family, logo=logo, icon=icon)


def _center_window(root: tkinter.Tk, *, row_count: int, logger: logging.Logger) -> int | None:
    """Dimensiona y centra la ventana; devuelve el ancho usado o ``None``.

    Si no hay display lo deja pasar y devuelve ``None`` para que el llamador
    use el ancho nominal en el calculo de `wraplength`.
    """
    import tkinter

    try:
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        width, height, x, y = compute_window_geometry(row_count, screen_width, screen_height)
        root.geometry(f"{width}x{height}+{x}+{y}")
        return width
    except (tkinter.TclError, AttributeError, RuntimeError) as exc:
        logger.debug("No se pudo centrar la ventana (%s).", exc)
        return None


def run_gui_menu(
    *,
    request: AppRunRequest,
    apps_config: AppsConfig,
    catalog: AppCatalog | None = None,
    logger: logging.Logger = LOGGER,
    tk_factory: Callable[[], tkinter.Tk] | None = None,
    identity_provider: IdentityProvider | None = None,
    policy: AppPolicy | None = None,
    camera_enumerator: CameraEnumerator | None = None,
) -> int:
    """Muestra el menu grafico y abre apps hasta que el usuario sale (0).

    La app elegida corre con la ventana oculta (`withdraw`) y al terminar se
    re-muestra (`deiconify`). Cerrar con la X, ESC o el boton Salir devuelve 0.
    `tk_factory` inyecta la clase Tk en tests (sin display real). Con
    `identity_provider` y `policy` (los inyecta el launcher real) las apps sin
    permiso se muestran con `[sin permiso]` y no se pueden abrir; sin ambas,
    el menu es el historico (sin filtro). `camera_enumerator` inyecta el
    descubridor de camaras en tests; por defecto se usa OpenCV (perezoso).
    """
    import tkinter

    from recognizer.cli.menu import resolve_runner

    resolved_catalog = catalog if catalog is not None else AppCatalog()
    engine = policy
    current: Identity | None = None
    if identity_provider is not None or engine is not None:
        if engine is None:
            engine = AllowAllPolicy()
        current = (
            identity_provider.current_identity()
            if identity_provider is not None
            else anonymous_identity()
        )
    rows = build_menu_rows(resolved_catalog, apps_config, identity=current, policy=engine)
    theme = DEFAULT_THEME

    tk_cls = tk_factory if tk_factory is not None else tkinter.Tk
    root = tk_cls()
    root.title(GUI_WINDOW_TITLE)
    root.configure(bg=theme.surface)
    root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
    root.resizable(True, True)
    window_width = _center_window(root, row_count=len(rows), logger=logger)

    branding = _apply_branding(root, logger=logger)
    display_family = branding.display_family
    body_family = _resolve_body_font(root, logger=logger)

    focusable: list[tuple[MenuRow, tkinter.Button]] = []
    focused_index = 0
    cameras: list[CameraInfo] = []
    selected_device: int | None = None

    def effective_request() -> AppRunRequest:
        """Request con la camara elegida en el selector (`device`)."""
        if selected_device is None:
            return request
        return replace(request, device=selected_device)

    def open_row(row: MenuRow) -> None:
        if row.app_id is None or not row.selectable:
            logger.info("'%s' no esta disponible %s.", row.title, row.label)
            return
        if engine is not None:
            fresh = (
                identity_provider.current_identity()
                if identity_provider is not None
                else anonymous_identity()
            )
            if not engine.can_launch(fresh, app_id=row.app_id):
                logger.warning(
                    "'%s' requiere un rol con permiso (tu rol: %s).",
                    row.title,
                    fresh.role.value,
                )
                return
        if row.app_id is AppId.FACE_AUTH:
            from recognizer.cli.face_menu_gui import run_face_submenu

            logger.info("Abriendo '%s'... (ESC para volver al menu)", row.title)
            root.withdraw()
            try:
                run_face_submenu(
                    effective_request(),
                    identity_provider=identity_provider,
                    logger=logger,
                )
            finally:
                root.deiconify()
            logger.info("Volviendo al menu principal.")
            return
        runner = resolve_runner(row.app_id)
        if runner is None:
            logger.error("No hay runner para '%s'.", row.app_id.value)
            return
        logger.info("Abriendo '%s'... (ESC/q para volver al menu)", row.title)
        root.withdraw()
        try:
            runner(effective_request())
        finally:
            root.deiconify()
        logger.info("Volviendo al menu principal.")

    def focus_at(index: int) -> None:
        nonlocal focused_index
        if not focusable:
            return
        focused_index = max(0, min(index, len(focusable) - 1))
        focusable[focused_index][1].focus_set()

    def open_focused() -> None:
        if not focusable:
            logger.info("No hay aplicaciones disponibles.")
            return
        open_row(focusable[focused_index][0])

    def close() -> None:
        root.destroy()

    header = tkinter.Frame(root, bg=theme.primary)
    header.pack(side=SIDE_TOP, fill=FILL_X)
    if branding.logo is not None:
        logo_label = tkinter.Label(header, image=branding.logo, bg=theme.primary, bd=BORDER_NONE)
        logo_label.pack(side=SIDE_LEFT, padx=(theme.pad_header, theme.space_3), pady=theme.space_3)
    title_box = tkinter.Frame(header, bg=theme.primary)
    title_box.pack(
        side=SIDE_LEFT,
        fill=FILL_BOTH,
        expand=True,
        padx=(BORDER_NONE, theme.pad_header),
        pady=theme.space_3,
    )
    tkinter.Label(
        title_box,
        text=GUI_HEADER_TITLE,
        font=(display_family, theme.size_display, FONT_WEIGHT_BOLD),
        fg=theme.primary_contrast,
        bg=theme.primary,
        anchor=ANCHOR_WEST,
    ).pack(fill=FILL_X)
    tkinter.Label(
        title_box,
        text=GUI_HEADER_SUBTITLE,
        font=(body_family, theme.size_body_small),
        fg=theme.primary_contrast,
        bg=theme.primary,
        anchor=ANCHOR_WEST,
    ).pack(fill=FILL_X)

    def detect_cameras() -> None:
        """Enumera las camaras (OpenCV perezoso) y selecciona la primera."""
        nonlocal selected_device
        if camera_enumerator is not None:
            enumerator: CameraEnumerator = camera_enumerator
        else:
            from recognizer.adapters.camera_discovery import OpenCVCameraEnumerator

            enumerator = OpenCVCameraEnumerator()
        try:
            found = enumerator.list_cameras()
        except Exception as exc:  # detectar jamas tumba el menu
            logger.warning("No se pudieron detectar las camaras (%s).", exc)
            return
        cameras.clear()
        cameras.extend(found)
        logger.info(GUI_CAMERA_LOG_TEMPLATE.format(count=len(cameras)))
        if cameras:
            selected_device = cameras[0].index
            cycle_button.configure(text=str(selected_device))
        else:
            selected_device = None
            cycle_button.configure(text=GUI_CAMERA_AUTO_TEXT)

    def cycle_camera() -> None:
        """Rota la camara seleccionada entre las detectadas."""
        nonlocal selected_device
        if not cameras:
            logger.info("Sin camaras detectadas; pulsa Detectar primero.")
            return
        indices = [info.index for info in cameras]
        if selected_device not in indices:
            selected_device = indices[0]
        else:
            selected_device = indices[(indices.index(selected_device) + 1) % len(indices)]
        cycle_button.configure(text=str(selected_device))

    camera_box = tkinter.Frame(header, bg=theme.primary)
    camera_box.pack(side=SIDE_RIGHT, padx=(BORDER_NONE, theme.pad_header), pady=theme.space_3)
    tkinter.Label(
        camera_box,
        text=GUI_CAMERA_LABEL,
        font=(body_family, theme.size_body_small, FONT_WEIGHT_BOLD),
        fg=theme.primary_contrast,
        bg=theme.primary,
        anchor=ANCHOR_WEST,
    ).pack(fill=FILL_X)
    camera_buttons = tkinter.Frame(camera_box, bg=theme.primary)
    camera_buttons.pack(fill=FILL_X)
    cycle_button = tkinter.Button(
        camera_buttons,
        text=GUI_CAMERA_AUTO_TEXT,
        command=cycle_camera,
        relief=RELIEF_RAISED,
        bd=BUTTON_BORDER_WIDTH,
        padx=theme.pad_button_x,
        pady=theme.space_1,
        font=(body_family, theme.size_body_small, FONT_WEIGHT_BOLD),
        bg=theme.surface_alt,
        fg=theme.text,
        activebackground=theme.surface,
        activeforeground=theme.text,
        cursor=CURSOR_HAND,
        takefocus=True,
        highlightthickness=FOCUS_HIGHLIGHT_WIDTH,
        highlightbackground=theme.primary,
        highlightcolor=theme.primary_contrast,
    )
    cycle_button.pack(side=SIDE_LEFT)
    detect_button = tkinter.Button(
        camera_buttons,
        text=GUI_CAMERA_DETECT_TEXT,
        command=detect_cameras,
        relief=RELIEF_RAISED,
        bd=BUTTON_BORDER_WIDTH,
        padx=theme.pad_button_x,
        pady=theme.space_1,
        font=(body_family, theme.size_body_small, FONT_WEIGHT_BOLD),
        bg=theme.surface_alt,
        fg=theme.text,
        activebackground=theme.surface,
        activeforeground=theme.text,
        cursor=CURSOR_HAND,
        takefocus=True,
        highlightthickness=FOCUS_HIGHLIGHT_WIDTH,
        highlightbackground=theme.primary,
        highlightcolor=theme.primary_contrast,
    )
    detect_button.pack(side=SIDE_LEFT, padx=(theme.space_1, BORDER_NONE))
    cycle_button.bind(EVENT_RETURN, _event_handler(cycle_camera, consume=True))
    cycle_button.bind(EVENT_SPACE, _event_handler(cycle_camera, consume=True))
    detect_button.bind(EVENT_RETURN, _event_handler(detect_cameras, consume=True))
    detect_button.bind(EVENT_SPACE, _event_handler(detect_cameras, consume=True))

    footer = tkinter.Frame(root, bg=theme.surface_alt)
    footer.pack(side=SIDE_BOTTOM, fill=FILL_X)
    tkinter.Label(
        footer,
        text=GUI_FOOTER_HINT,
        font=(body_family, theme.size_body_small),
        fg=theme.text_muted,
        bg=theme.surface_alt,
        anchor=ANCHOR_WEST,
    ).pack(side=SIDE_LEFT, padx=theme.pad_footer, pady=theme.pad_footer)
    exit_button = tkinter.Button(
        footer,
        text=GUI_EXIT_TEXT,
        command=close,
        relief=RELIEF_RAISED,
        bd=BUTTON_BORDER_WIDTH,
        padx=theme.pad_button_x,
        pady=theme.space_1,
        font=(body_family, theme.size_body, FONT_WEIGHT_BOLD),
        bg=theme.surface_alt,
        fg=theme.text,
        activebackground=theme.surface,
        activeforeground=theme.text,
        cursor=CURSOR_HAND,
        takefocus=True,
        highlightthickness=FOCUS_HIGHLIGHT_WIDTH,
        highlightbackground=theme.surface_alt,
        highlightcolor=theme.primary_strong,
    )
    exit_button.pack(side=SIDE_RIGHT, padx=theme.pad_footer, pady=theme.pad_footer)
    open_button = tkinter.Button(
        footer,
        text=GUI_OPEN_TEXT,
        command=open_focused,
        relief=RELIEF_RAISED,
        bd=BUTTON_BORDER_WIDTH,
        padx=theme.pad_button_x,
        pady=theme.space_1,
        font=(body_family, theme.size_body, FONT_WEIGHT_BOLD),
        bg=theme.primary,
        fg=theme.primary_contrast,
        activebackground=theme.primary_strong,
        activeforeground=theme.primary_contrast,
        cursor=CURSOR_HAND,
        takefocus=True,
        highlightthickness=FOCUS_HIGHLIGHT_WIDTH,
        highlightbackground=theme.surface_alt,
        highlightcolor=theme.primary_strong,
    )
    open_button.pack(side=SIDE_RIGHT, padx=(BORDER_NONE, theme.space_1), pady=theme.pad_footer)
    exit_button.bind(EVENT_RETURN, _event_handler(close, consume=True))
    exit_button.bind(EVENT_SPACE, _event_handler(close, consume=True))
    open_button.bind(EVENT_RETURN, _event_handler(open_focused, consume=True))
    open_button.bind(EVENT_SPACE, _event_handler(open_focused, consume=True))

    body_outer = tkinter.Frame(root, bg=theme.surface)
    body_outer.pack(
        side=SIDE_TOP, fill=FILL_BOTH, expand=True, padx=theme.pad_body, pady=theme.space_4
    )
    canvas = tkinter.Canvas(
        body_outer, bg=theme.surface, highlightthickness=BORDER_NONE, bd=BORDER_NONE
    )
    scrollbar = tkinter.Scrollbar(body_outer, orient=ORIENT_VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side=SIDE_RIGHT, fill=FILL_Y)
    canvas.pack(side=SIDE_LEFT, fill=FILL_BOTH, expand=True)
    body = tkinter.Frame(canvas, bg=theme.surface)
    body_window = canvas.create_window(
        (BORDER_NONE, BORDER_NONE), window=body, anchor=ANCHOR_NORTH_WEST
    )
    body.bind(
        EVENT_CONFIGURE,
        lambda _event: canvas.configure(scrollregion=canvas.bbox(TK_ALL)),
    )
    canvas.bind(
        EVENT_CONFIGURE,
        lambda event: canvas.itemconfigure(body_window, width=event.width),
    )
    tkinter.Label(
        body,
        text=GUI_APPS_SECTION,
        font=(display_family, theme.size_display_small, FONT_WEIGHT_BOLD),
        fg=theme.text_muted,
        bg=theme.surface,
        anchor=ANCHOR_WEST,
    ).pack(fill=FILL_X, pady=(BORDER_NONE, theme.space_2))

    button_wraplength = _button_wraplength(
        window_width if window_width is not None else WINDOW_WIDTH
    )
    for row in rows:
        selectable = row.selectable and row.app_id is not None
        row_frame = tkinter.Frame(body, bg=theme.surface)
        row_frame.pack(fill=FILL_X, padx=theme.space_1, pady=theme.pad_row)
        button = tkinter.Button(
            row_frame,
            text=BUTTON_TEXT_TEMPLATE.format(
                number=row.number, title=row.title, description=row.description
            ),
            command=partial(open_row, row),
            anchor=ANCHOR_WEST,
            justify=JUSTIFY_LEFT,
            wraplength=button_wraplength,
            relief=RELIEF_RAISED,
            bd=BUTTON_BORDER_WIDTH,
            padx=theme.pad_button_x,
            pady=theme.pad_button_y,
            font=(body_family, theme.size_body, FONT_WEIGHT_BOLD),
            bg=theme.surface_alt if selectable else theme.surface,
            fg=theme.text if selectable else theme.text_muted,
            activebackground=theme.primary_soft,
            activeforeground=theme.text,
            disabledforeground=theme.text_muted,
            cursor=CURSOR_HAND if selectable else CURSOR_ARROW,
            takefocus=selectable,
            highlightthickness=FOCUS_HIGHLIGHT_WIDTH,
            highlightbackground=theme.surface,
            highlightcolor=theme.primary_strong,
            state=STATE_NORMAL if selectable else STATE_DISABLED,
        )
        badge = tkinter.Label(
            row_frame,
            text=row.label,
            font=(display_family, theme.size_badge, FONT_WEIGHT_BOLD),
            bg=_badge_background(row.availability, theme),
            fg=theme.text if row.denied else badge_foreground(row.availability, theme),
            padx=theme.pad_badge_x,
            pady=theme.pad_badge_y,
            relief=RELIEF_RAISED,
            bd=BADGE_BORDER_WIDTH,
        )
        badge.pack(side=SIDE_RIGHT, padx=(theme.space_2, theme.space_3))
        button.pack(side=SIDE_LEFT, fill=FILL_X, expand=True)
        if selectable:
            open_row_action = partial(open_row, row)
            button.bind(EVENT_RETURN, _event_handler(open_row_action, consume=True))
            button.bind(EVENT_SPACE, _event_handler(open_row_action, consume=True))
            button.bind(EVENT_DOUBLE_CLICK, _event_handler(open_row_action, consume=False))
            focusable.append((row, button))

    if focusable:
        focus_at(0)

    root.protocol(EVENT_CLOSE_WINDOW, close)
    root.bind(EVENT_ESCAPE, lambda _event: close())
    root.bind(EVENT_RETURN, lambda _event: open_focused())
    root.bind(EVENT_SPACE, lambda _event: open_focused())
    root.bind(EVENT_UP, lambda _event: focus_at(focused_index - 1))
    root.bind(EVENT_DOWN, lambda _event: focus_at(focused_index + 1))
    root.bind(EVENT_MOUSEWHEEL, lambda event: _scroll_canvas(canvas, event))

    try:
        root.mainloop()
    except KeyboardInterrupt:
        logger.info("Interrumpido; saliendo del menu.")
    return 0
