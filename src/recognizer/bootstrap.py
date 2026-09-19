"""Composition root: pipeline, camara y acciones a partir de la configuracion."""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from recognizer.adapters.chrome_link_opener import ChromeLinkOpener
from recognizer.adapters.chromium_cdp import ChromiumCdpBrowser
from recognizer.adapters.overlay_opencv import (
    GestureOverlay,
    LandmarkOverlay,
    MenuOverlay,
    PointerOverlay,
)
from recognizer.adapters.pynput_keys import PynputKeySender
from recognizer.adapters.pynput_mouse import PynputMouseController
from recognizer.adapters.subprocess_command import SubprocessCommandRunner
from recognizer.adapters.subprocess_script import SubprocessScriptRunner
from recognizer.core.actions.browser import OpenTabAction, TabPressAction, TabSeekAction
from recognizer.core.actions.decorators import (
    ActionGate,
    DebouncedAction,
    GatedAction,
    LoggedAction,
)
from recognizer.core.actions.links import OpenLinksAction
from recognizer.core.actions.local import CommandAction, HotkeyAction, MediaKeyAction
from recognizer.core.actions.menus import Menu
from recognizer.core.actions.script import ScriptAction
from recognizer.core.actions.scroll import ScrollAction
from recognizer.core.config import (
    ActionConfig,
    ActionsConfig,
    AppConfig,
    BrowserConfig,
    CameraConfig,
    CommandActionConfig,
    GestureConfig,
    HotkeyActionConfig,
    MediaKeyActionConfig,
    OpenLinksActionConfig,
    OpenTabActionConfig,
    PointerConfig,
    ScriptActionConfig,
    ScrollActionConfig,
    TabPressActionConfig,
    TabSeekActionConfig,
)
from recognizer.core.domain.action import Action, ScriptRequest
from recognizer.core.domain.browser import TabKey
from recognizer.core.domain.gesture import GestureCatalog, GestureId
from recognizer.core.domain.pointer import PointerCalibration
from recognizer.core.errors import ActionError, RecognizerError
from recognizer.core.pipeline.builder import Pipeline, PipelineBuilder
from recognizer.core.pipeline.gesture_detection import GestureDetectionProcessor
from recognizer.core.pipeline.gesture_stabilization import GestureStabilizerProcessor
from recognizer.core.pipeline.landmark_rules import LandmarkRule, LandmarkRuleProcessor
from recognizer.core.pipeline.pointer_click_detection import PointerClickDetectionProcessor
from recognizer.core.pipeline.pointer_detection import PointerDetectionProcessor
from recognizer.core.pointer.clicker import PointerClicker
from recognizer.core.pointer.mover import PointerMover
from recognizer.core.pointer.smoothing import create_smoothing
from recognizer.core.ports.browser_tabs import BrowserTabs
from recognizer.core.ports.command_runner import CommandRunner
from recognizer.core.ports.event_bus import EventBus
from recognizer.core.ports.gesture_classifier import GestureClassifier
from recognizer.core.ports.key_sender import KeySender
from recognizer.core.ports.link_opener import LinkOpener
from recognizer.core.ports.mouse_controller import MouseController
from recognizer.core.ports.script_runner import ScriptRunner


@dataclass(frozen=True, slots=True)
class ActionBindings:
    """Mapeo global, menus compuestos y gate compartido que los habilita."""

    mapping: Mapping[GestureId, Action]
    gate: ActionGate | None
    menus: tuple[Menu, ...] = ()


def _wrap_action(
    *,
    action: Action,
    gate: ActionGate,
    cooldown_seconds: float,
    logger: logging.Logger | None,
    spec: ActionConfig | None = None,
) -> Action:
    """Envuelve una accion con log, debounce y gate compartido.

    Si la config de la accion declara ``cooldown_seconds``, este prevalece
    sobre el cooldown global (p. ej. el scroll necesita ticks mas rapidos).
    """
    override: float | None = getattr(spec, "cooldown_seconds", None)
    effective_cooldown = override if override is not None else cooldown_seconds
    return GatedAction(
        DebouncedAction(
            LoggedAction(action, logger=logger),
            cooldown_seconds=effective_cooldown,
        ),
        gate=gate,
    )


def _extract_repeat_intervals(
    actions: ActionsConfig,
    catalog: GestureCatalog,
) -> dict[GestureId, float]:
    """Extrae los intervalos de repeticion de las acciones que lo configuran."""
    intervals: dict[GestureId, float] = {}
    for label, spec in actions.mappings.items():
        repeat = getattr(spec, "repeat_seconds", None)
        if repeat is not None and repeat > 0:
            gesture_id = catalog.require(label)
            intervals[gesture_id] = repeat
    return intervals


def build_pipeline(
    *,
    classifier: GestureClassifier | None,
    bus: EventBus,
    gestures: GestureConfig,
    pointer: PointerConfig | None = None,
    catalog: GestureCatalog | None = None,
    menus: Sequence[Menu] | None = None,
    repeat_intervals: Mapping[GestureId, float] | None = None,
) -> Pipeline:
    """Construye el pipeline de deteccion, estabilizacion, puntero y overlay."""
    builder = PipelineBuilder()
    if classifier is not None:
        gesture_catalog = catalog or GestureCatalog.from_labels(
            custom_labels=gestures.custom_labels,
            rule_names=tuple(gestures.rules),
        )
        builder.add(GestureDetectionProcessor(classifier=classifier, bus=bus))
        if gestures.rules:
            builder.add(
                LandmarkRuleProcessor(
                    rules=tuple(
                        LandmarkRule(
                            gesture=gesture_catalog.require(name),
                            config=rule_config,
                        )
                        for name, rule_config in gestures.rules.items()
                    ),
                    thresholds=gestures.rule_thresholds,
                    priority=gestures.rules_priority,
                )
            )
        builder.add(
            GestureStabilizerProcessor(
                bus=bus,
                stabilization_frames=gestures.stabilization_frames,
                release_frames=gestures.release_frames,
                min_gesture_confidence=gestures.min_gesture_confidence,
                repeat_intervals=repeat_intervals,
            )
        )
        if pointer is not None and pointer.enabled:
            builder.add(
                PointerDetectionProcessor(
                    bus=bus,
                    calibration=PointerCalibration(
                        x_min=pointer.active_zone.x_min,
                        x_max=pointer.active_zone.x_max,
                        y_min=pointer.active_zone.y_min,
                        y_max=pointer.active_zone.y_max,
                        mirror_x=pointer.mirror_x,
                    ),
                    smoothing=create_smoothing(kind=pointer.smoothing, alpha=pointer.alpha),
                    activation_gesture=gesture_catalog.require(pointer.activation_gesture),
                )
            )
            builder.add(
                PointerClickDetectionProcessor(
                    bus=bus,
                    activation_gesture=gesture_catalog.require(pointer.activation_gesture),
                    thumb_open_threshold=pointer.thumb_open_threshold,
                )
            )
        builder.add(LandmarkOverlay())
        builder.add(GestureOverlay())
        if menus:
            builder.add(MenuOverlay(menus))
        if pointer is not None and pointer.enabled:
            builder.add(PointerOverlay())
    return builder.build()


def resolve_camera_config(*, app_config: AppConfig, device_override: int | None) -> CameraConfig:
    """Aplica el override de device_index si se indico."""
    if device_override is None:
        return app_config.camera
    if device_override < 0:
        msg = "--device debe ser mayor o igual a 0."
        raise RecognizerError(msg)
    return CameraConfig(
        device_index=device_override,
        width=app_config.camera.width,
        height=app_config.camera.height,
        target_fps=app_config.camera.target_fps,
    )


def build_action_bindings(
    *,
    actions: ActionsConfig,
    catalog: GestureCatalog,
    key_sender: KeySender | None = None,
    command_runner: CommandRunner | None = None,
    script_runner: ScriptRunner | None = None,
    link_opener: LinkOpener | None = None,
    browser_tabs: BrowserTabs | None = None,
    browser_config: BrowserConfig | None = None,
    mouse_controller: MouseController | None = None,
    gate: ActionGate | None = None,
    logger: logging.Logger | None = None,
) -> ActionBindings:
    """Construye el mapeo y los menus de acciones decoradas y el gate compartido.

    El catalogo traduce las etiquetas configuradas a ``GestureId``. Sin mapeos
    ni menus no se instancian adapters reales de teclado ni subprocess. Si se
    recibe un gate, se reutiliza para que CLI comparta un unico interruptor.
    """
    if not actions.mappings and not actions.menus:
        return ActionBindings(mapping={}, gate=gate)

    sender = key_sender or PynputKeySender()
    runner = command_runner or SubprocessCommandRunner()
    script = script_runner or SubprocessScriptRunner()
    opener = link_opener or ChromeLinkOpener()
    scroll_mouse = mouse_controller
    if scroll_mouse is None and _has_scroll_actions(actions):
        # Controlador dedicado al scroll (no se reutiliza el del puntero).
        scroll_mouse = PynputMouseController()
    shared_gate = gate if gate is not None else ActionGate()

    resolved_browser: BrowserTabs | None = browser_tabs
    if resolved_browser is None and browser_config is not None:
        _has_browser_actions = any(
            getattr(spec, "tab", None) is not None
            for spec in (
                *actions.mappings.values(),
                *(opt for menu in actions.menus.values() for opt in menu.options.values()),
            )
        )
        if _has_browser_actions:
            from recognizer.adapters.chromium import autodetect_browser

            detected = autodetect_browser(executable_override=browser_config.executable)
            if detected is not None:
                from pathlib import Path

                base = (
                    Path(browser_config.user_data_dir)
                    if browser_config.user_data_dir
                    else Path.cwd()
                )
                from recognizer.core.domain.browser import TabSpec

                specs = {
                    TabKey(name): TabSpec(key=TabKey(name), url=tab.url, match=tab.match)
                    for name, tab in browser_config.tabs.items()
                }
                resolved_browser = ChromiumCdpBrowser(
                    tabs=specs,
                    detected=detected,
                    profile_dir=base,
                    port=browser_config.debugging_port,
                )

    def decorated(spec: ActionConfig) -> Action:
        action = _build_action(
            spec=spec,
            key_sender=sender,
            command_runner=runner,
            script_runner=script,
            link_opener=opener,
            browser_tabs=resolved_browser,
            browser_config=browser_config,
            mouse_controller=scroll_mouse,
        )
        return _wrap_action(
            action=action,
            gate=shared_gate,
            cooldown_seconds=actions.cooldown_seconds,
            logger=logger,
            spec=spec,
        )

    mapping: dict[GestureId, Action] = {}
    for label, spec in actions.mappings.items():
        mapping[catalog.require(label)] = decorated(spec)

    menus: list[Menu] = []
    for name, menu_config in actions.menus.items():
        options: dict[GestureId, Action] = {}
        for label, spec in menu_config.options.items():
            options[catalog.require(label)] = decorated(spec)
        menus.append(
            Menu(
                name=name,
                hand=menu_config.hand,
                modifier=catalog.require(menu_config.modifier),
                consume_trigger=menu_config.consume_trigger,
                options=options,
            )
        )
    return ActionBindings(mapping=mapping, gate=shared_gate, menus=tuple(menus))


def _has_scroll_actions(actions: ActionsConfig) -> bool:
    """Indica si alguna accion global o de menu es de tipo scroll."""
    return any(
        isinstance(spec, ScrollActionConfig)
        for spec in (
            *actions.mappings.values(),
            *(opt for menu in actions.menus.values() for opt in menu.options.values()),
        )
    )


def build_pointer_mover(
    *,
    pointer: PointerConfig,
    gate: ActionGate | None = None,
    controller: MouseController | None = None,
    logger: logging.Logger | None = None,
) -> PointerMover | None:
    """Construye el mover del puntero si esta habilitado; el caller lo suscribe."""
    if not pointer.enabled:
        return None
    return PointerMover(
        controller=controller or PynputMouseController(),
        gate=gate,
        logger=logger,
    )


def build_pointer_clicker(
    *,
    pointer: PointerConfig,
    gate: ActionGate | None = None,
    controller: MouseController | None = None,
    logger: logging.Logger | None = None,
) -> PointerClicker | None:
    """Construye el clicker del puntero si esta habilitado; el caller lo suscribe."""
    if not pointer.enabled:
        return None
    return PointerClicker(
        controller=controller or PynputMouseController(),
        gate=gate,
        logger=logger,
    )


def _build_action(
    *,
    spec: ActionConfig,
    key_sender: KeySender,
    command_runner: CommandRunner,
    script_runner: ScriptRunner,
    link_opener: LinkOpener,
    browser_tabs: BrowserTabs | None = None,
    browser_config: BrowserConfig | None = None,
    mouse_controller: MouseController | None = None,
) -> Action:
    match spec:
        case MediaKeyActionConfig(key=key):
            return MediaKeyAction(key=key, sender=key_sender)
        case HotkeyActionConfig(keys=keys):
            return HotkeyAction(keys=keys, sender=key_sender)
        case CommandActionConfig(argv=argv):
            return CommandAction(argv=argv, runner=command_runner)
        case ScriptActionConfig():
            return ScriptAction(
                request=ScriptRequest(
                    path=spec.path,
                    args=spec.args,
                    interpreter=spec.interpreter,
                    working_dir=spec.working_dir,
                    blocking=spec.blocking,
                    timeout_seconds=spec.timeout_seconds,
                    env=None,
                ),
                runner=script_runner,
                pass_context=spec.pass_context,
            )
        case OpenLinksActionConfig(urls=urls, browser=browser):
            return OpenLinksAction(
                urls=urls,
                opener=link_opener if browser is None else ChromeLinkOpener(executable=browser),
            )
        case OpenTabActionConfig(tab=tab_name, urls=urls):
            if browser_tabs is None:
                msg = "Se requiere un navegador CDP para open_tab"
                raise ActionError(msg)
            tab_key = TabKey(tab_name)
            effective_urls = urls
            if not effective_urls and browser_config is not None:
                tab_cfg = browser_config.tabs.get(tab_name)
                if tab_cfg is not None:
                    effective_urls = (tab_cfg.url,)
            return OpenTabAction(
                urls=effective_urls,
                browser=browser_tabs,
                tab=tab_key,
            )
        case TabSeekActionConfig(tab=tab_name, fraction=fraction):
            if browser_tabs is None:
                msg = "Se requiere un navegador CDP para tab_seek"
                raise ActionError(msg)
            return TabSeekAction(tab=TabKey(tab_name), fraction=fraction, browser=browser_tabs)
        case TabPressActionConfig(tab=tab_name, keys=keys):
            if browser_tabs is None:
                msg = "Se requiere un navegador CDP para tab_press"
                raise ActionError(msg)
            return TabPressAction(tab=TabKey(tab_name), keys=keys, browser=browser_tabs)
        case ScrollActionConfig(direction=direction, lines=lines):
            return ScrollAction(
                direction=direction,
                lines=lines,
                controller=mouse_controller or PynputMouseController(),
            )
    msg = f"Accion no soportada: {type(spec).__name__}"
    raise ActionError(msg)
