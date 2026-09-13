"""Acciones locales disparadas por gestos confirmados."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from recognizer.core.domain.gesture import GestureId
from recognizer.core.domain.hand import Handedness


class MediaKey(StrEnum):
    """Teclas multimedia que las acciones pueden pulsar."""

    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    VOLUME_MUTE = "volume_mute"
    PLAY_PAUSE = "play_pause"
    NEXT_TRACK = "next_track"
    PREVIOUS_TRACK = "previous_track"


class ScriptInterpreter(StrEnum):
    """Interprete con el que ejecutar un script local."""

    AUTO = "auto"
    PYTHON = "python"
    POWERSHELL = "powershell"
    CMD = "cmd"
    BASH = "bash"
    DIRECT = "direct"


@dataclass(frozen=True, slots=True)
class ScriptRequest:
    """Descripcion de un script local que una accion puede ejecutar."""

    path: str
    args: tuple[str, ...] = ()
    interpreter: ScriptInterpreter = ScriptInterpreter.AUTO
    working_dir: str | None = None
    blocking: bool = False
    timeout_seconds: float = 0.0
    env: Mapping[str, str] | None = None


@dataclass(frozen=True, slots=True)
class ActionContext:
    """Datos del gesto confirmado que dispara una accion."""

    gesture: GestureId
    confidence: float
    handedness: Handedness
    timestamp: float


class Action(Protocol):
    """Ejecuta una accion local ante un gesto confirmado (Command)."""

    def execute(self, context: ActionContext) -> None:
        """Ejecuta la accion con el contexto del gesto confirmado."""
        ...
