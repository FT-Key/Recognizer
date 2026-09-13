"""Composition root: pipeline, camara y acciones a partir de la configuracion."""

import logging
from collections.abc import Mapping
from dataclasses import dataclass

from recognizer.adapters.chrome_link_opener import ChromeLinkOpener
from recognizer.adapters.overlay_opencv import GestureOverlay, LandmarkOverlay, PointerOverlay
from recognizer.adapters.pynput_keys import PynputKeySender
from recognizer.adapters.pynput_mouse import PynputMouseController
from recognizer.adapters.subprocess_command import SubprocessCommandRunner
from recognizer.adapters.subprocess_script import SubprocessScriptRunner
from recognizer.core.actions.decorators import (
    ActionGate,
    DebouncedAction,
    GatedAction,
    LoggedAction,
)
from recognizer.core.actions.links import OpenLinksAction
from recognizer.core.actions.local import CommandAction, HotkeyAction, MediaKeyAction
from recognizer.core.actions.script import ScriptAction
from recognizer.core.config import (
    ActionConfig,
    ActionsConfig,
    AppConfig,
    CameraConfig,
    CommandActionConfig,
    GestureConfig,
    HotkeyActionConfig,
    MediaKeyActionConfig,
    OpenLinksActionConfig,
    PointerConfig,
    ScriptActionConfig,
)
from recognizer.core.domain.action import Action, ScriptRequest
from recognizer.core.domain.gesture import GestureCatalog, GestureId
from recognizer.core.domain.pointer import PointerCalibration
from recognizer.core.errors import ActionError, RecognizerError
from recognizer.core.pipeline.builder import Pipeline, PipelineBuilder
from recognizer.core.pipeline.gesture_detection import GestureDetectionProcessor
from recognizer.core.pipeline.gesture_stabilization import GestureStabilizerProcessor
from recognizer.core.pipeline.landmark_rules import LandmarkRule, LandmarkRuleProcessor
from recognizer.core.pipeline.pointer_detection import PointerDetectionProcessor
from recognizer.core.pointer.mover import PointerMover
from recognizer.core.pointer.smoothing import create_smoothing
from recognizer.core.ports.command_runner import CommandRunner
from recognizer.core.ports.event_bus import EventBus
from recognizer.core.ports.gesture_classifier import GestureClassifier
from recognizer.core.ports.key_sender import KeySender
from recognizer.core.ports.link_opener import LinkOpener
from recognizer.core.ports.mouse_controller import MouseController
from recognizer.core.ports.script_runner import ScriptRunner


@dataclass(frozen=True, slots=True)
class ActionBindings:
    """Mapeo de gestos a acciones y gate compartido que las habilita."""

    mapping: Mapping[GestureId, Action]
    gate: ActionGate | None


def build_pipeline(
    *,
    classifier: GestureClassifier | None,
    bus: EventBus,
    gestures: GestureConfig,
    pointer: PointerConfig | None = None,
    catalog: GestureCatalog | None = None,
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
        builder.add(LandmarkOverlay())
        builder.add(GestureOverlay())
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
    gate: ActionGate | None = None,
    logger: logging.Logger | None = None,
) -> ActionBindings:
    """Construye el mapeo de acciones decoradas y el gate compartido.

    El catalogo traduce las etiquetas configuradas a ``GestureId``. Sin mapeos
    no se instancian adapters reales de teclado ni subprocess. Si se recibe un
    gate, se reutiliza para que CLI comparta un unico interruptor.
    """
    if not actions.mappings:
        return ActionBindings(mapping={}, gate=gate)

    sender = key_sender or PynputKeySender()
    runner = command_runner or SubprocessCommandRunner()
    script = script_runner or SubprocessScriptRunner()
    opener = link_opener or ChromeLinkOpener()
    shared_gate = gate if gate is not None else ActionGate()
    mapping: dict[GestureId, Action] = {}
    for label, spec in actions.mappings.items():
        action = _build_action(
            spec=spec,
            key_sender=sender,
            command_runner=runner,
            script_runner=script,
            link_opener=opener,
        )
        mapping[catalog.require(label)] = GatedAction(
            DebouncedAction(
                LoggedAction(action, logger=logger),
                cooldown_seconds=actions.cooldown_seconds,
            ),
            gate=shared_gate,
        )
    return ActionBindings(mapping=mapping, gate=shared_gate)


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


def _build_action(
    *,
    spec: ActionConfig,
    key_sender: KeySender,
    command_runner: CommandRunner,
    script_runner: ScriptRunner,
    link_opener: LinkOpener,
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
    msg = f"Accion no soportada: {type(spec).__name__}"
    raise ActionError(msg)
