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
from collections import Counter
from collections.abc import Sequence
from contextlib import ExitStack
from pathlib import Path

import cv2

from recognizer.adapters.camera_opencv import OpenCVCamera
from recognizer.adapters.mediapipe_gesture_classifier import MediaPipeGestureClassifier
from recognizer.bootstrap import (
    ActionBindings,
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
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--device", type=int, default=None, help="Sobrescribe device_index.")
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
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    log_banner(LOGGER)
    show_window = not args.no_window

    try:
        if not show_window and args.frames <= 0:
            msg = "Sin ventana no hay ESC: usa --frames > 0 junto con --no-window."
            raise RecognizerError(msg)
        with log_step(LOGGER, "Cargando configuracion"):
            app_config = load_config(args.config)
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

            if actions_active:
                bindings = build_action_bindings(
                    actions=app_config.actions,
                    catalog=app_config.gesture_catalog(),
                    gate=gate,
                )
                dispatcher = GestureActionDispatcher(
                    actions=bindings.mapping,
                    menus=bindings.menus,
                )
                bus.subscribe(GestureDetected, dispatcher.handle)
                bus.subscribe(GestureReleased, dispatcher.handle)
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
                catalog=app_config.gesture_catalog(),
                menus=bindings.menus,
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
