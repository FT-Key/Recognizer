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
import os
import sys
import tempfile
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
from recognizer.cli.console import log_banner, log_step
from recognizer.cli.runtime import RuntimeCallbacks, run_camera_loop
from recognizer.core.actions.decorators import ActionGate
from recognizer.core.actions.dispatcher import GestureActionDispatcher
from recognizer.core.bus import InProcessEventBus
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

DEFAULT_CONFIG_PATH = Path("config.yaml")
WINDOW_NAME = "Recognizer"
TOGGLE_KEY = ord("a")
NO_CONFIRMED_GESTURES = "ninguno"
APP_NAME = "recognizer"
APP_VERSION = "0.1.0"
# En el .exe (frozen) el servidor de salud arranca por defecto para que la web
# detecte la app; en desarrollo queda desactivado (0) para no abrir puertos.
DEFAULT_HEALTH_PORT_FROZEN = 8765
DEFAULT_HEALTH_PORT_SOURCE = 0
# Log a archivo junto al ejecutable cuando esta empaquetado (util para depurar
# cierres inesperados del .exe, que no dejan consola visible al usuario final).
LOGS_DIRNAME = "logs"
LOG_FILENAME = "recognizer.log"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _is_frozen() -> bool:
    """Indica si corremos dentro de un ejecutable empaquetado (PyInstaller)."""
    return bool(getattr(sys, "frozen", False))


def _default_config_path() -> Path:
    """Resuelve config.yaml junto al ejecutable cuando esta empaquetado."""
    if _is_frozen():
        return Path(sys.executable).parent / DEFAULT_CONFIG_PATH
    return DEFAULT_CONFIG_PATH


def _default_health_port() -> int:
    """Puerto de salud por defecto segun el modo de ejecucion."""
    if _is_frozen():
        return DEFAULT_HEALTH_PORT_FROZEN
    return DEFAULT_HEALTH_PORT_SOURCE


def _prepare_workspace(config_arg: Path) -> Path:
    """Resuelve la ruta de config y fija el CWD para rutas relativas del YAML.

    Cuando la app corre empaquetada, los recursos (config.yaml y models/) viven
    junto al ejecutable; cambiar el CWD alli hace que ``models/*.task`` del YAML
    se resuelvan sin tocar la configuracion.
    """
    base_dir = Path(sys.executable).parent if _is_frozen() else Path.cwd()
    config_path = config_arg if config_arg.is_absolute() else base_dir / config_arg
    if config_path.parent != Path.cwd():
        os.chdir(config_path.parent)
    return config_path


def _default_log_file() -> Path | None:
    """Ruta del log por defecto: junto al .exe si esta empaquetado, si no ninguno."""
    if _is_frozen():
        return Path(sys.executable).parent / LOGS_DIRNAME / LOG_FILENAME
    return None


def _resolve_log_file(log_file: Path) -> Path:
    """Resuelve la ruta del log y garantiza que su carpeta exista.

    Si la carpeta junto al ejecutable no es escribible (p. ej. Program Files),
    cae al directorio temporal del sistema para no perder el diagnostico.
    """
    candidate = log_file if log_file.is_absolute() else Path.cwd() / log_file
    try:
        candidate.parent.mkdir(parents=True, exist_ok=True)
        return candidate
    except OSError:
        fallback = Path(tempfile.gettempdir()) / LOGS_DIRNAME / LOG_FILENAME
        fallback.parent.mkdir(parents=True, exist_ok=True)
        return fallback


def _configure_logging(*, verbose: bool, log_file: Path | None) -> Path | None:
    """Configura logging a consola y, si se indica, a archivo. Devuelve el log usado."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    if log_file is None:
        return None

    resolved = _resolve_log_file(log_file)
    handler = logging.FileHandler(resolved, encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    logging.getLogger().addHandler(handler)
    return resolved


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


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del comando `recognizer`."""
    args = _build_parser().parse_args(argv)
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
    show_window = not args.no_window

    try:
        if not show_window and args.frames <= 0:
            msg = "Sin ventana no hay ESC: usa --frames > 0 junto con --no-window."
            raise RecognizerError(msg)
        with log_step(LOGGER, "Cargando configuracion"):
            config_path = _prepare_workspace(args.config)
            app_config = load_config(config_path)
            camera_config = resolve_camera_config(
                app_config=app_config, device_override=args.device
            )
        bus = InProcessEventBus()
        stats = _Stats()
        bus.subscribe(HandsDetected, stats.handle)
        bus.subscribe(GestureDetected, stats.handle)
        bus.subscribe(GestureReleased, stats.handle)
        bus.subscribe(PointerMoved, stats.handle)

        with log_step(LOGGER, "Preparando gestos, acciones y puntero"):
            actions_active = not args.no_actions and bool(
                app_config.actions.mappings or app_config.actions.menus
            )
            pointer_active = app_config.pointer.enabled and not args.no_pointer
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
            if args.health_port > 0:
                health = HealthServer(
                    port=args.health_port,
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
                max_frames=args.frames,
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


if __name__ == "__main__":
    sys.exit(main())
