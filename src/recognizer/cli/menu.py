"""Menu de aplicaciones (launcher multi-app).

Solo importa dependencias livianas: cada app se importa de forma perezosa al
lanzarse, de modo que abrir el menu no carga MediaPipe/YOLO ni abre la camara.
Salir de una app (ESC/q) devuelve el control al menu, no cierra el programa.
"""

import logging
from collections.abc import Callable
from pathlib import Path

from recognizer.cli.console import BANNER_BORDER, BANNER_WIDTH, configure_logging, log_banner
from recognizer.cli.paths import default_config_path, default_log_file
from recognizer.core.config import AppConfig, AppsConfig, FaceAuthConfig
from recognizer.core.constants import ANONYMOUS_FACE_ID
from recognizer.core.domain.app import (
    AppAvailability,
    AppCatalog,
    AppGroup,
    AppId,
    AppInfo,
    AppRunRequest,
)
from recognizer.core.domain.identity import DEFAULT_PERMISSIONS as DEFAULT_ROLE_PERMISSIONS
from recognizer.core.domain.identity import (
    AllowAllPolicy,
    AppPolicy,
    Identity,
    PolicyEngine,
    anonymous_identity,
    normalize_overrides,
)
from recognizer.core.errors import ConfigError
from recognizer.core.ports.identity_provider import IdentityProvider
from recognizer.settings import load_config

LOGGER = logging.getLogger("recognizer.menu")

PROMPT = "Selecciona una aplicacion: "
EXIT_CHOICES = frozenset({"0", "q", "salir", "exit"})
MENU_TITLE = "R E C O G N I Z E R  -  MENU"
MENU_SUBTITLE = "elige una aplicacion (ESC/q dentro de una app vuelve aqui)"
EXIT_LINE = "  0) Salir"
BACK_LINE = "  0) Volver"
OTHER_APPS_TITLE = "Otras apps"
LABEL_OTHER_APPS = "[abrir]"
TITLE_COLUMN = 32

LABEL_AVAILABLE = "[disponible]"
LABEL_DISABLED = "[deshabilitada]"
LABEL_COMING_SOON = "[proximamente]"
LABEL_NO_PERMISSION = "[sin permiso]"

AppRunner = Callable[[AppRunRequest], int]
GuiRunner = Callable[[AppRunRequest, AppsConfig, AppCatalog | None], int]


def _build_policy(face_config: FaceAuthConfig) -> PolicyEngine:
    """Motor de permisos: matriz por defecto + override ``face_auth.permissions``."""
    merged = dict(DEFAULT_ROLE_PERMISSIONS)
    merged.update(normalize_overrides(face_config.permissions))
    return PolicyEngine(permissions=merged)


def _identity_from_config(app_config: AppConfig) -> tuple[IdentityProvider, AppPolicy]:
    """Proveedor de sesion y politica desde la config ya cargada.

    En modo abierto (``require_login: false``) y sin sesion devuelve la
    politica ``AllowAllPolicy`` para no romper los flujos sin enrolar. Solo
    lee JSON del disco (liviano): no carga modelos de vision.
    """
    from recognizer.adapters.file_face_repository import FileFaceRepository
    from recognizer.adapters.file_identity_provider import (
        AllowAllIdentityProvider,
        FileIdentityProvider,
    )

    try:
        repository = FileFaceRepository(app_config.face_auth.store_dir)
    except OSError as exc:
        LOGGER.warning("Almacen facial no disponible (%s); modo abierto.", exc)
        return AllowAllIdentityProvider(), AllowAllPolicy()
    provider: IdentityProvider = FileIdentityProvider(
        app_config.face_auth.store_dir,
        repository,
        session_timeout_seconds=app_config.face_auth.session_timeout_seconds,
    )
    identity = provider.current_identity()
    if not app_config.face_auth.require_login and identity.face_id == ANONYMOUS_FACE_ID:
        return provider, AllowAllPolicy()
    return provider, _build_policy(app_config.face_auth)


def resolve_launcher_identity(config_path: Path) -> tuple[IdentityProvider, AppPolicy]:
    """Carga la config y resuelve (proveedor, politica) del launcher.

    Raises:
        ConfigError: si la configuracion es invalida.
        OSError: si el almacen no se puede preparar.
    """
    return _identity_from_config(load_config(config_path))


def _default_gui_runner(
    request: AppRunRequest,
    apps_config: AppsConfig,
    catalog: AppCatalog | None,
) -> int:
    """GuiRunner real: delega en el menu grafico (import perezoso)."""
    from recognizer.cli.menu_gui import run_gui_menu

    try:
        provider, policy = resolve_launcher_identity(request.config_path)
    except (ConfigError, OSError) as exc:
        LOGGER.info("sin identidad; usando menu sin filtro de permisos (%s)", exc)
        return run_gui_menu(request=request, apps_config=apps_config, catalog=catalog)
    return run_gui_menu(
        request=request,
        apps_config=apps_config,
        catalog=catalog,
        identity_provider=provider,
        policy=policy,
    )


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
        case AppId.ANTI_INTRUDER:
            from recognizer.cli.apps.anti_intruder import run_anti_intruder

            return run_anti_intruder
        case AppId.POSTURE:
            from recognizer.cli.apps.posture import run_posture

            return run_posture
        case AppId.FACE_AUTH:
            from recognizer.cli.apps.face_auth import run_face_auth

            return run_face_auth
        case AppId.ASSISTANCE:
            from recognizer.cli.apps.assistance import run_assistance

            return run_assistance
        case AppId.LOITERING:
            from recognizer.cli.apps.loitering import run_loitering

            return run_loitering
        case AppId.VACANCY:
            from recognizer.cli.apps.vacancy import run_vacancy

            return run_vacancy
        case AppId.VEHICLE_COUNTER:
            from recognizer.cli.apps.vehicle_counter import run_vehicle_counter

            return run_vehicle_counter
        case AppId.PRIVACY_BLUR:
            from recognizer.cli.apps.privacy_blur import run_privacy_blur

            return run_privacy_blur
        case AppId.GENDER_AGE:
            from recognizer.cli.apps.gender_age import run_gender_age

            return run_gender_age
        case AppId.FALL_DETECTOR:
            from recognizer.cli.apps.fall_detector import run_fall_detector

            return run_fall_detector
        case AppId.DROWSINESS:
            from recognizer.cli.apps.drowsiness import run_drowsiness

            return run_drowsiness
        case AppId.OCR_READER:
            from recognizer.cli.apps.ocr_reader import run_ocr_reader

            return run_ocr_reader
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


def render_catalog(
    catalog: AppCatalog,
    apps_config: AppsConfig,
    *,
    group: AppGroup | None = None,
    identity: Identity | None = None,
    policy: AppPolicy | None = None,
) -> str:
    """Construye el texto multilinea del menu con las apps y su estado.

    ``group=None`` lista todas las apps (historico). Con ``AppGroup.MAIN`` lista
    las principales y agrega al final la entrada "Otras apps"; con
    ``AppGroup.OTHER`` lista solo las secundarias. Con ``identity`` y ``policy``
    las apps no permitidas se marcan con ``[sin permiso]``.
    """
    lines = [
        BANNER_BORDER,
        MENU_TITLE.center(BANNER_WIDTH),
        MENU_SUBTITLE.center(BANNER_WIDTH),
        BANNER_BORDER,
    ]
    infos = catalog.apps if group is None else catalog.apps_in_group(group)
    for number, info in enumerate(infos, start=1):
        availability = catalog.availability(info.app_id, enabled=apps_config.enabled)
        label = availability_label(info, availability)
        if (
            policy is not None
            and identity is not None
            and not policy.can_launch(identity, app_id=info.app_id)
        ):
            label = f"{label} {LABEL_NO_PERMISSION}"
        lines.append(f"  {number}) {info.title:<{TITLE_COLUMN}} {label}")
    if group is AppGroup.MAIN:
        number = len(infos) + 1
        lines.append(f"  {number}) {OTHER_APPS_TITLE:<{TITLE_COLUMN}} {LABEL_OTHER_APPS}")
    lines.append(BACK_LINE if group is AppGroup.OTHER else EXIT_LINE)
    return "\n".join(lines)


def _launch_info(
    info: AppInfo,
    *,
    catalog: AppCatalog,
    apps_config: AppsConfig,
    request: AppRunRequest,
    engine: AppPolicy | None,
    current: Identity | None,
    logger: logging.Logger,
) -> None:
    """Ejecuta la app si esta disponible y permitida; informa si no."""
    availability = catalog.availability(info.app_id, enabled=apps_config.enabled)
    if availability is AppAvailability.COMING_SOON:
        logger.info("'%s' aun no esta implementada (proximamente).", info.title)
        return
    if availability is AppAvailability.DISABLED:
        logger.info("'%s' esta deshabilitada en config.yaml (apps.enabled).", info.title)
        return
    if (
        engine is not None
        and current is not None
        and not engine.can_launch(current, app_id=info.app_id)
    ):
        logger.warning(
            "'%s' requiere un rol con permiso (tu rol: %s).",
            info.title,
            current.role.value,
        )
        return
    runner = resolve_runner(info.app_id)
    if runner is None:
        logger.error("No hay runner para '%s'.", info.app_id.value)
        return
    logger.info("Abriendo '%s'... (ESC/q para volver al menu)", info.title)
    runner(request)
    logger.info("Volviendo al menu principal.")


def run_menu(
    *,
    request: AppRunRequest,
    apps_config: AppsConfig,
    catalog: AppCatalog | None = None,
    input_fn: Callable[[str], str] | None = None,
    logger: logging.Logger = LOGGER,
    identity_provider: IdentityProvider | None = None,
    policy: AppPolicy | None = None,
) -> int:
    """Muestra el menu en bucle hasta que el usuario sale.

    El menu principal lista las apps de ``AppGroup.MAIN`` mas una entrada
    "Otras apps" que abre el submenu con las secundarias. Cada app corre de
    forma sincrona; al terminar (ESC/q) se vuelve a mostrar el menu. Devuelve 0
    al salir. Con ``identity_provider`` y ``policy`` las apps sin permiso se
    marcan y su lanzamiento se bloquea; sin ambas, el menu es el historico.
    """
    resolved_catalog = catalog if catalog is not None else AppCatalog()
    reader = input_fn if input_fn is not None else input
    engine = policy
    if identity_provider is not None and engine is None:
        engine = AllowAllPolicy()
    main_infos = resolved_catalog.apps_in_group(AppGroup.MAIN)
    other_infos = resolved_catalog.apps_in_group(AppGroup.OTHER)

    def current_identity() -> Identity | None:
        if engine is None:
            return None
        return (
            identity_provider.current_identity()
            if identity_provider is not None
            else anonymous_identity()
        )

    def read_choice() -> str | None:
        try:
            return reader(PROMPT)
        except EOFError:
            logger.info("Entrada cerrada; saliendo del menu.")
            return None
        except KeyboardInterrupt:
            logger.info("Interrumpido; saliendo del menu.")
            return None

    def show(*, group: AppGroup) -> None:
        identity = current_identity()
        if engine is not None:
            logger.info(
                "\n%s",
                render_catalog(
                    resolved_catalog, apps_config, group=group, identity=identity, policy=engine
                ),
            )
        else:
            logger.info("\n%s", render_catalog(resolved_catalog, apps_config, group=group))

    def menu_loop(infos: tuple[AppInfo, ...], *, group: AppGroup, allow_other: bool) -> bool:
        """Un bucle de menu; devuelve True si hay que salir del launcher."""
        while True:
            show(group=group)
            raw = read_choice()
            if raw is None:
                return True
            choice = raw.strip().lower()
            if choice == "0":
                if group is AppGroup.OTHER:
                    logger.info("Volviendo al menu principal.")
                    return False
                logger.info("Hasta luego.")
                return True
            if choice in EXIT_CHOICES:
                logger.info("Hasta luego.")
                return True
            if not choice.isdigit():
                logger.warning("Opcion no valida: %r", raw)
                continue
            number = int(choice)
            if allow_other and number == len(infos) + 1:
                if menu_loop(other_infos, group=AppGroup.OTHER, allow_other=False):
                    return True
                continue
            if not 1 <= number <= len(infos):
                logger.warning("No existe la opcion %s.", choice)
                continue
            _launch_info(
                infos[number - 1],
                catalog=resolved_catalog,
                apps_config=apps_config,
                request=request,
                engine=engine,
                current=current_identity(),
                logger=logger,
            )

    menu_loop(main_infos, group=AppGroup.MAIN, allow_other=True)
    return 0


def run_launcher(
    *,
    list_only: bool = False,
    use_gui: bool = True,
    gui_runner: GuiRunner | None = None,
    identity_provider: IdentityProvider | None = None,
    policy: AppPolicy | None = None,
) -> int:
    """Arranca el menu (o solo lista las apps) sin cargar librerias de vision.

    Con ``use_gui=False`` va directo al menu de consola. Con ``use_gui=True``
    usa ``gui_runner`` si se inyecta (dobles en tests) o el menu grafico real
    por defecto. Si el runner grafico falla con ``ImportError`` (sin tkinter)
    o ``tkinter.TclError`` (sin display) —lo lance el runner real o un doble
    inyectado—, cae al menu de consola. ``identity_provider``/``policy`` son
    inyectables para tests; por defecto se resuelven de la config (liviano,
    sin modelos de vision).
    """
    configure_logging(verbose=False, log_file=default_log_file())
    log_banner(LOGGER)

    config_path = default_config_path()
    try:
        app_config = load_config(config_path)
    except ConfigError as exc:
        LOGGER.warning("Configuracion no disponible (%s); usando valores por defecto.", exc)
        app_config = AppConfig()

    provider = identity_provider
    engine = policy
    if provider is None and engine is None:
        try:
            provider, engine = _identity_from_config(app_config)
        except (ConfigError, OSError) as exc:
            LOGGER.warning("Identidad no disponible (%s); modo abierto.", exc)
    current = provider.current_identity() if provider is not None else None

    catalog = AppCatalog()
    if list_only:
        LOGGER.info(
            "\n%s", render_catalog(catalog, app_config.apps, identity=current, policy=engine)
        )
        return 0

    request = AppRunRequest(config_path=config_path, show_window=True)
    if use_gui:
        try:
            import tkinter
        except ImportError as exc:
            LOGGER.info("sin display; usando menú de consola (%s)", exc)
        else:
            runner = gui_runner if gui_runner is not None else _default_gui_runner
            try:
                return runner(request, app_config.apps, catalog)
            except tkinter.TclError as exc:
                LOGGER.info("sin display; usando menú de consola (%s)", exc)
    return run_menu(
        request=request,
        apps_config=app_config.apps,
        catalog=catalog,
        identity_provider=provider,
        policy=engine,
    )
