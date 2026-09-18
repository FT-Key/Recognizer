"""Menu de aplicaciones (launcher multi-app).

Solo importa dependencias livianas: cada app se importa de forma perezosa al
lanzarse, de modo que abrir el menu no carga MediaPipe/YOLO ni abre la camara.
Salir de una app (ESC/q) devuelve el control al menu, no cierra el programa.
"""

import logging
from collections.abc import Callable

from recognizer.cli.console import BANNER_BORDER, BANNER_WIDTH, configure_logging, log_banner
from recognizer.cli.paths import default_config_path, default_log_file
from recognizer.core.config import AppConfig, AppsConfig
from recognizer.core.domain.app import (
    AppAvailability,
    AppCatalog,
    AppId,
    AppInfo,
    AppRunRequest,
)
from recognizer.core.errors import ConfigError
from recognizer.settings import load_config

LOGGER = logging.getLogger("recognizer.menu")

PROMPT = "Selecciona una aplicacion: "
EXIT_CHOICES = frozenset({"0", "q", "salir", "exit"})
MENU_TITLE = "R E C O G N I Z E R  -  MENU"
MENU_SUBTITLE = "elige una aplicacion (ESC/q dentro de una app vuelve aqui)"
EXIT_LINE = "  0) Salir"
TITLE_COLUMN = 32

LABEL_AVAILABLE = "[disponible]"
LABEL_DISABLED = "[deshabilitada]"
LABEL_COMING_SOON = "[proximamente]"

AppRunner = Callable[[AppRunRequest], int]


def resolve_runner(app_id: AppId) -> AppRunner | None:
    """Devuelve el runner de la app (import perezoso) o ``None`` si no existe.

    Al implementar una app nueva, agrega aqui su rama y su modulo de runner en
    `cli/`; el import se hace dentro del `match` para no cargar la app si no se
    selecciona.
    """
    match app_id:
        case AppId.GESTURES:
            from recognizer.cli.app import run_gestures

            return run_gestures
        case AppId.PEOPLE_COUNTER:
            from recognizer.cli.apps.people_counter import run_people_counter

            return run_people_counter
        case _:
            return None


def availability_label(info: AppInfo, availability: AppAvailability) -> str:
    """Etiqueta legible del estado de una app, con su trabajo previo si aplica."""
    if availability is AppAvailability.AVAILABLE:
        return LABEL_AVAILABLE
    if availability is AppAvailability.DISABLED:
        return LABEL_DISABLED
    if info.preparation is not None:
        return f"{LABEL_COMING_SOON} - requiere {info.preparation.value}"
    return LABEL_COMING_SOON


def render_catalog(catalog: AppCatalog, apps_config: AppsConfig) -> str:
    """Construye el texto multilinea del menu con todas las apps y su estado."""
    lines = [
        BANNER_BORDER,
        MENU_TITLE.center(BANNER_WIDTH),
        MENU_SUBTITLE.center(BANNER_WIDTH),
        BANNER_BORDER,
    ]
    for number, info in enumerate(catalog.apps, start=1):
        availability = catalog.availability(info.app_id, enabled=apps_config.enabled)
        label = availability_label(info, availability)
        lines.append(f"  {number}) {info.title:<{TITLE_COLUMN}} {label}")
    lines.append(EXIT_LINE)
    return "\n".join(lines)


def run_menu(
    *,
    request: AppRunRequest,
    apps_config: AppsConfig,
    catalog: AppCatalog | None = None,
    input_fn: Callable[[str], str] | None = None,
    logger: logging.Logger = LOGGER,
) -> int:
    """Muestra el menu en bucle hasta que el usuario sale.

    Cada app se ejecuta de forma sincrona; al terminar (ESC/q) se vuelve a
    mostrar el menu. Devuelve 0 al salir.
    """
    resolved_catalog = catalog if catalog is not None else AppCatalog()
    reader = input_fn if input_fn is not None else input

    while True:
        logger.info("\n%s", render_catalog(resolved_catalog, apps_config))
        try:
            raw = reader(PROMPT)
        except EOFError:
            logger.info("Entrada cerrada; saliendo del menu.")
            return 0
        except KeyboardInterrupt:
            logger.info("Interrumpido; saliendo del menu.")
            return 0

        choice = raw.strip().lower()
        if choice in EXIT_CHOICES:
            logger.info("Hasta luego.")
            return 0
        if not choice.isdigit():
            logger.warning("Opcion no valida: %r", raw)
            continue

        info = resolved_catalog.by_number(int(choice))
        if info is None:
            logger.warning("No existe la opcion %s.", choice)
            continue

        availability = resolved_catalog.availability(info.app_id, enabled=apps_config.enabled)
        if availability is AppAvailability.COMING_SOON:
            logger.info("'%s' aun no esta implementada (proximamente).", info.title)
            continue
        if availability is AppAvailability.DISABLED:
            logger.info("'%s' esta deshabilitada en config.yaml (apps.enabled).", info.title)
            continue

        runner = resolve_runner(info.app_id)
        if runner is None:
            logger.error("No hay runner para '%s'.", info.app_id.value)
            continue

        logger.info("Abriendo '%s'... (ESC/q para volver al menu)", info.title)
        runner(request)
        logger.info("Volviendo al menu principal.")


def run_launcher(*, list_only: bool = False) -> int:
    """Arranca el menu (o solo lista las apps) sin cargar librerias de vision."""
    configure_logging(verbose=False, log_file=default_log_file())
    log_banner(LOGGER)

    config_path = default_config_path()
    try:
        app_config = load_config(config_path)
    except ConfigError as exc:
        LOGGER.warning("Configuracion no disponible (%s); usando valores por defecto.", exc)
        app_config = AppConfig()

    catalog = AppCatalog()
    if list_only:
        LOGGER.info("\n%s", render_catalog(catalog, app_config.apps))
        return 0

    request = AppRunRequest(config_path=config_path, show_window=True)
    return run_menu(request=request, apps_config=app_config.apps, catalog=catalog)
