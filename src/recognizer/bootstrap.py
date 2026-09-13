"""Composition root: pipeline, camara y acciones a partir de la configuracion."""

import logging
from collections.abc import Mapping
from dataclasses import dataclass

from recognizer.adapters.overlay_opencv import GestureOverlay, LandmarkOverlay
from recognizer.adapters.pynput_keys import PynputKeySender
from recognizer.adapters.subprocess_command import SubprocessCommandRunner
from recognizer.core.actions.decorators import (
    ActionGate,
    DebouncedAction,
    GatedAction,
    LoggedAction,
)
from recognizer.core.actions.local import CommandAction, HotkeyAction, MediaKeyAction
from recognizer.core.config import (
    ActionConfig,
    ActionsConfig,
    AppConfig,
    CameraConfig,
    CommandActionConfig,
    GestureConfig,
    HotkeyActionConfig,
    MediaKeyActionConfig,
)
from recognizer.core.domain.action import Action
from recognizer.core.domain.gesture import GestureName
from recognizer.core.errors import ActionError, RecognizerError
from recognizer.core.pipeline.builder import Pipeline, PipelineBuilder
from recognizer.core.pipeline.gesture_detection import GestureDetectionProcessor
from recognizer.core.pipeline.gesture_stabilization import GestureStabilizerProcessor
from recognizer.core.ports.command_runner import CommandRunner
from recognizer.core.ports.event_bus import EventBus
from recognizer.core.ports.gesture_classifier import GestureClassifier
from recognizer.core.ports.key_sender import KeySender


@dataclass(frozen=True, slots=True)
class ActionBindings:
    """Mapeo de gestos a acciones y gate compartido que las habilita."""

    mapping: Mapping[GestureName, Action]
    gate: ActionGate | None


def build_pipeline(
    *,
    classifier: GestureClassifier | None,
    bus: EventBus,
    gestures: GestureConfig,
) -> Pipeline:
    """Construye el pipeline de deteccion, estabilizacion y overlay."""
    builder = PipelineBuilder()
    if classifier is not None:
        builder.add(GestureDetectionProcessor(classifier=classifier, bus=bus))
        builder.add(
            GestureStabilizerProcessor(
                bus=bus,
                stabilization_frames=gestures.stabilization_frames,
                release_frames=gestures.release_frames,
                min_gesture_confidence=gestures.min_gesture_confidence,
            )
        )
        builder.add(LandmarkOverlay())
        builder.add(GestureOverlay())
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
    key_sender: KeySender | None = None,
    command_runner: CommandRunner | None = None,
    logger: logging.Logger | None = None,
) -> ActionBindings:
    """Construye el mapeo de acciones decoradas y el gate compartido.

    Sin mapeos no se instancian adapters reales de teclado ni subprocess.
    """
    if not actions.mappings:
        return ActionBindings(mapping={}, gate=None)

    sender = key_sender or PynputKeySender()
    runner = command_runner or SubprocessCommandRunner()
    gate = ActionGate()
    mapping: dict[GestureName, Action] = {}
    for gesture, spec in actions.mappings.items():
        action = _build_action(spec=spec, key_sender=sender, command_runner=runner)
        mapping[gesture] = GatedAction(
            DebouncedAction(
                LoggedAction(action, logger=logger),
                cooldown_seconds=actions.cooldown_seconds,
            ),
            gate=gate,
        )
    return ActionBindings(mapping=mapping, gate=gate)


def _build_action(
    *,
    spec: ActionConfig,
    key_sender: KeySender,
    command_runner: CommandRunner,
) -> Action:
    match spec:
        case MediaKeyActionConfig(key=key):
            return MediaKeyAction(key=key, sender=key_sender)
        case HotkeyActionConfig(keys=keys):
            return HotkeyAction(keys=keys, sender=key_sender)
        case CommandActionConfig(argv=argv):
            return CommandAction(argv=argv, runner=command_runner)
    msg = f"Accion no soportada: {type(spec).__name__}"
    raise ActionError(msg)
