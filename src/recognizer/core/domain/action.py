"""Acciones locales disparadas por gestos confirmados."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from recognizer.core.domain.gesture import GestureName
from recognizer.core.domain.hand import Handedness


class MediaKey(StrEnum):
    """Teclas multimedia que las acciones pueden pulsar."""

    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    VOLUME_MUTE = "volume_mute"
    PLAY_PAUSE = "play_pause"
    NEXT_TRACK = "next_track"
    PREVIOUS_TRACK = "previous_track"


@dataclass(frozen=True, slots=True)
class ActionContext:
    """Datos del gesto confirmado que dispara una accion."""

    gesture: GestureName
    confidence: float
    handedness: Handedness
    timestamp: float


class Action(Protocol):
    """Ejecuta una accion local ante un gesto confirmado (Command)."""

    def execute(self, context: ActionContext) -> None:
        """Ejecuta la accion con el contexto del gesto confirmado."""
        ...
