"""Aplicacion local: camara, gestos y acciones.

Uso:
    uv run recognizer                  # ventana en vivo con acciones (ESC o q para salir)
    uv run recognizer --no-actions     # deteccion y overlay sin ejecutar acciones
    uv run recognizer --no-window --frames 30
    uv run recognizer --device 1
    uv run recognizer --verbose        # log DEBUG para calibrar gestos
"""

import argparse
import logging
import sys
import threading
from collections import Counter
from collections.abc import Sequence
from contextlib import ExitStack
from pathlib import Path
from types import TracebackType

import cv2

from recognizer.adapters.camera_opencv import OpenCVCamera
from recognizer.adapters.health_server import HealthServer
from recognizer.adapters.mediapipe_gesture_classifier import MediaPipeGestureClassifier
from recognizer.adapters.pynput_mouse import screen_size
from recognizer.bootstrap import (
    ActionBindings,
    _extract_repeat_intervals,
    build_action_bindings,
    build_pipeline,
    build_pointer_clicker,
    build_pointer_mover,
    resolve_camera_config,
)
from recognizer.cli import paths
from recognizer.cli.console import configure_logging, log_banner, log_step
from recognizer.cli.paths import (
    default_config_path,
    default_health_port,
    default_log_file,
    is_frozen,
    prepare_workspace,
    resolve_log_file,
)
from recognizer.cli.runtime import RuntimeCallbacks, run_camera_loop
from recognizer.core.actions.decorators import ActionGate
from recognizer.core.actions.dispatcher import GestureActionDispatcher
from recognizer.core.bus import InProcessEventBus
from recognizer.core.domain.app import AppRunRequest
from recognizer.core.domain.events import (
    DomainEvent,
    GestureDetected,
    GestureHeld,
    GestureReleased,
    HandsDetected,
    PointerClicked,
    PointerMoved,
)
from recognizer.core.domain.gesture import GestureId
from recognizer.core.errors import RecognizerError
from recognizer.core.pipeline.context import FrameContext
from recognizer.settings import load_config

LOGGER = logging.getLogger("recognizer.app")

# Alias internos: mantienen el nombre historico usado por tests y por el resto
# del modulo, delegando la implementacion en `cli/paths.py` (modulo liviano).
_is_frozen = is_frozen
_default_config_path = default_config_path
_default_health_port = default_health_port
_default_log_file = default_log_file
_prepare_workspace = prepare_workspace
_configure_logging = configure_logging
_resolve_log_file = resolve_log_file

# Re-export de constantes de rutas usadas historicamente por tests y el .exe.
DEFAULT_CONFIG_PATH = paths.DEFAULT_CONFIG_PATH
DEFAULT_HEALTH_PORT_FROZEN = paths.DEFAULT_HEALTH_PORT_FROZEN
DEFAULT_HEALTH_PORT_SOURCE = paths.DEFAULT_HEALTH_PORT_SOURCE
LOGS_DIRNAME = paths.LOGS_DIRNAME

WINDOW_NAME = "Recognizer"
TOGGLE_KEY = ord("a")
NO_CONFIRMED_GESTURES = "ninguno"
APP_NAME = "recognizer"
APP_VERSION = "0.1.0"


def _install_exception_hooks(logger: logging.Logger) -> None:
    """Registra crashes del hilo principal y de hilos secundarios en el log."""

    def report(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: TracebackType | None,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.critical("Excepcion no controlada", exc_info=(exc_type, exc_value, exc_tb))

    def report_thread(args: threading.ExceptHookArgs) -> None:
        exc_value = args.exc_value if args.exc_value is not None else RuntimeError("desconocido")
        report(args.exc_type, exc_value, args.exc_traceback)

    sys.excepthook = report
    threading.excepthook = report_thread


def _log_screen_size() -> None:
    """Registra el tamano de pantalla; diagnostica el puntero sin lanzar el gesto."""
    try:
        width, height = screen_size()
    except Exception:
        # Si esto falla (p. ej. falta el runtime de Tk en el .exe), el puntero
        # fallara: se registra el error para poder diagnosticarlo.
        LOGGER.exception("No se pudo resolver el tamano de pantalla (el puntero fallara)")
    else:
        LOGGER.info("Pantalla detectada: %dx%d", width, height)


HUD_POSITION = (10, 30)
HUD_FONT = cv2.FONT_HERSHEY_SIMPLEX
HUD_SCALE = 0.8
HUD_THICKNESS = 2
HUD_ENABLED_TEXT = "Acciones: ON"
HUD_DISABLED_TEXT = "Acciones: OFF"
HUD_POINTER_ENABLED_TEXT = "Puntero: ON"
HUD_POINTER_DISABLED_TEXT = "Puntero: OFF"
HUD_ENABLED_COLOR_BGR = (0, 200, 0)
HUD_DISABLED_COLOR_BGR = (0, 0, 255)


class _Stats:
    """Cuenta eventos de manos, gestos confirmados y puntero publicados al bus."""

    def __init__(self) -> None:
        self.hands_events = 0
        self.max_hands = 0
        self.detected_events = 0
        self.released_events = 0
        self.pointer_events = 0
        self.confirmed: Counter[GestureId] = Counter()

    def handle(self, event: DomainEvent) -> None:
        """Actualiza los contadores segun el tipo de evento."""
        match event:
            case HandsDetected(hands=hands):
                self.hands_events += 1
                self.max_hands = max(self.max_hands, len(hands))
            case GestureDetected(gesture=gesture):
                self.detected_events += 1
                self.confirmed[gesture] += 1
            case GestureReleased():
                self.released_events += 1
            case PointerMoved():
                self.pointer_events += 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="recognizer",
        description="Abre la camara, reconoce gestos y ejecuta acciones locales.",
    )
    parser.add_argument("--config", type=Path, default=_default_config_path())
    parser.add_argument("--device", type=int, default=None, help="Sobrescribe device_index.")
    parser.add_argument(
        "--health-port",
        type=int,
        default=_default_health_port(),
        help="Puerto local de salud para que la web detecte la app (0 = desactivado).",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=0,
        help="Numero de fotogramas antes de salir (0 = hasta ESC/q en modo ventana).",
    )
    parser.add_argument("--no-window", action="store_true", help="No abre ventana (modo check).")
    parser.add_argument(
        "--no-actions",
        action="store_true",
        help="No ejecuta acciones locales aunque haya mapeos.",
    )
    parser.add_argument(
        "--no-pointer",
        action="store_true",
        help="No mueve el puntero aunque este habilitado en config.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="No ejecuta acciones de navegador (open_tab/tab_seek/tab_press).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Log detallado (DEBUG) para calibrar gestos y umbrales.",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=_default_log_file(),
        help="Ruta del archivo de log (por defecto: logs/recognizer.log junto al .exe).",
    )
    parser.add_argument(
        "--list-apps",
        action="store_true",
        help="Lista las aplicaciones del menu y sale (sin abrir camara).",
    )
    return parser


def _format_confirmed(confirmed: Counter[GestureId]) -> str:
    if not confirmed:
        return NO_CONFIRMED_GESTURES
    return ", ".join(f"{name.value}={count}" for name, count in confirmed.items())


def _actions_state(gate: ActionGate | None) -> str:
    if gate is None:
        return "inactivas"
    return "activadas" if gate.enabled else "desactivadas"


def _pointer_state(enabled: bool) -> str:
    return "activado" if enabled else "desactivado"


def run_gestures(
    request: AppRunRequest,
    *,
    health_port: int | None = None,
    no_actions: bool = False,
    no_pointer: bool = False,
    no_browser: bool = False,
) -> int:
    """Ejecuta la app de reconocimiento de gestos.

    Pensada para el launcher: al salir (ESC/q) devuelve el control al llamador
    en lugar de terminar el proceso. Devuelve 0 si termino bien, 1 si fallo.
    """
    show_window = request.show_window
    resolved_health_port = default_health_port() if health_port is None else health_port

    try:
        if not show_window and request.max_frames <= 0:
            msg = "Sin ventana no hay ESC: usa --frames > 0 junto con --no-window."
            raise RecognizerError(msg)
        with log_step(LOGGER, "Cargando configuracion"):
            config_path = _prepare_workspace(request.config_path)
            app_config = load_config(config_path)
            camera_config = resolve_camera_config(
                app_config=app_config, device_override=request.device
            )
        bus = InProcessEventBus()
        stats = _Stats()
        bus.subscribe(HandsDetected, stats.handle)
        bus.subscribe(GestureDetected, stats.handle)
        bus.subscribe(GestureReleased, stats.handle)
        bus.subscribe(PointerMoved, stats.handle)

        with log_step(LOGGER, "Preparando gestos, acciones y puntero"):
            actions_active = not no_actions and bool(
                app_config.actions.mappings or app_config.actions.menus
            )
            pointer_active = app_config.pointer.enabled and not no_pointer
            browser_active = not no_browser and bool(app_config.browser.tabs)
            gate: ActionGate | None = ActionGate() if (actions_active or pointer_active) else None
            bindings = ActionBindings(mapping={}, gate=gate)
            if pointer_active:
                _log_screen_size()

            catalog = app_config.gesture_catalog()
            repeat_intervals = _extract_repeat_intervals(app_config.actions, catalog)

            if actions_active:
                bindings = build_action_bindings(
                    actions=app_config.actions,
                    catalog=catalog,
                    gate=gate,
                    browser_config=app_config.browser if browser_active else None,
                )
                dispatcher = GestureActionDispatcher(
                    actions=bindings.mapping,
                    menus=bindings.menus,
                )
                bus.subscribe(GestureDetected, dispatcher.handle)
                bus.subscribe(GestureReleased, dispatcher.handle)
                bus.subscribe(GestureHeld, dispatcher.handle)
            if pointer_active:
                mover = build_pointer_mover(pointer=app_config.pointer, gate=gate)
                if mover is not None:
                    bus.subscribe(PointerMoved, mover.handle)
                clicker = build_pointer_clicker(pointer=app_config.pointer, gate=gate)
                if clicker is not None:
                    bus.subscribe(PointerClicked, clicker.handle)

            classifier = MediaPipeGestureClassifier(app_config.gestures)
            pipeline = build_pipeline(
                classifier=classifier,
                bus=bus,
                gestures=app_config.gestures,
                pointer=app_config.pointer if pointer_active else None,
                catalog=catalog,
                menus=bindings.menus,
                repeat_intervals=repeat_intervals,
            )

        def _on_key(pressed: int) -> None:
            if pressed == TOGGLE_KEY and gate is not None:
                if gate.toggle():
                    LOGGER.info("Acciones activadas")
                else:
                    LOGGER.info("Acciones desactivadas")

        def _on_context(context: FrameContext) -> None:
            if gate is None:
                return
            enabled = gate.enabled
            if actions_active:
                text = HUD_ENABLED_TEXT if enabled else HUD_DISABLED_TEXT
            else:
                text = HUD_POINTER_ENABLED_TEXT if enabled else HUD_POINTER_DISABLED_TEXT
            cv2.putText(
                context.frame.data,
                text,
                HUD_POSITION,
                HUD_FONT,
                HUD_SCALE,
                HUD_ENABLED_COLOR_BGR if enabled else HUD_DISABLED_COLOR_BGR,
                HUD_THICKNESS,
            )

        def _on_progress(count: int, fps: float) -> None:
            LOGGER.info(
                "Fotogramas: %d | FPS medio: %.1f | Manos max: %d | Gestos confirmados: %d",
                count,
                fps,
                stats.max_hands,
                stats.detected_events,
            )

        with ExitStack() as stack:
            if resolved_health_port > 0:
                health = HealthServer(
                    port=resolved_health_port,
                    app_name=APP_NAME,
                    version=APP_VERSION,
                )
                try:
                    bound_port = health.start()
                except OSError as exc:
                    LOGGER.warning("No se pudo abrir el puerto de salud: %s", exc)
                else:
                    stack.callback(health.stop)
                    LOGGER.info(
                        "Deteccion web disponible en http://127.0.0.1:%d/health", bound_port
                    )
            with log_step(LOGGER, f"Abriendo camara (device={camera_config.device_index})"):
                camera = stack.enter_context(OpenCVCamera(camera_config))
            with log_step(LOGGER, "Cargando modelo de gestos"):
                stack.enter_context(classifier)
            LOGGER.info("Listo. Pulsa ESC o q para salir.")
            frames, fps = run_camera_loop(
                camera,
                pipeline=pipeline,
                window_name=WINDOW_NAME,
                show_window=show_window,
                max_frames=request.max_frames,
                callbacks=RuntimeCallbacks(
                    on_key=_on_key,
                    on_context=_on_context,
                    on_progress=_on_progress,
                ),
            )
    except RecognizerError as exc:
        LOGGER.error("La app fallo: %s", exc)
        return 1
    finally:
        if show_window:
            cv2.destroyAllWindows()

    LOGGER.info(
        "App OK: %d fotogramas, %.1f FPS medio, maximo de manos: %d, gestos confirmados: %s "
        "(HandsDetected: %d, GestureDetected: %d, GestureReleased: %d, PointerMoved: %d). "
        "Acciones: %s. Puntero: %s.",
        frames,
        fps,
        stats.max_hands,
        _format_confirmed(stats.confirmed),
        stats.hands_events,
        stats.detected_events,
        stats.released_events,
        stats.pointer_events,
        _actions_state(gate) if actions_active else "inactivas",
        _pointer_state(pointer_active and gate is not None and gate.enabled),
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del comando `recognizer`.

    Sin argumentos abre el menu de aplicaciones; con flags ejecuta la app de
    gestos directamente (comportamiento historico).
    """
    resolved = list(sys.argv[1:] if argv is None else argv)
    if not resolved:
        from recognizer.cli.menu import run_launcher

        return run_launcher()

    args = _build_parser().parse_args(resolved)
    if args.list_apps:
        from recognizer.cli.menu import run_launcher

        return run_launcher(list_only=True)

    log_file = _configure_logging(verbose=args.verbose, log_file=args.log_file)
    _install_exception_hooks(LOGGER)
    log_banner(LOGGER)
    if log_file is not None:
        LOGGER.info("Registrando en %s", log_file)
    LOGGER.info(
        "%s %s | frozen=%s | cwd=%s",
        APP_NAME,
        APP_VERSION,
        _is_frozen(),
        Path.cwd(),
    )
    return run_gestures(
        AppRunRequest(
            config_path=args.config,
            device=args.device,
            max_frames=args.frames,
            show_window=not args.no_window,
        ),
        health_port=args.health_port,
        no_actions=args.no_actions,
        no_pointer=args.no_pointer,
        no_browser=args.no_browser,
    )


if __name__ == "__main__":
    sys.exit(main())
