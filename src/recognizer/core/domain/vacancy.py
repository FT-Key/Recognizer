"""Deteccion de ausencia / zona vacia (dominio puro).

El ``VacancyMonitor`` detecta cuando no hay personas visibles en la camara
durante mas de ``absence_threshold_seconds`` segundos. Util para museos,
galerias o salas que deben tener al menos una persona presente.
"""

from dataclasses import dataclass

from recognizer.core.constants import (
    DEFAULT_VACANCY_CONFIRM_FRAMES,
    DEFAULT_VACANCY_RELEASE_FRAMES,
)
from recognizer.core.domain.tracking import TrackedDetection
from recognizer.core.errors import ConfigError


@dataclass(frozen=True, slots=True)
class VacancySnapshot:
    """Estado de ausencia en un instante."""

    active: bool
    people_count: int


class VacancyMonitor:
    """Detecta ausencia de personas con debounce por fotogramas.

    La alerta se activa tras ``confirm_frames`` fotogramas consecutivos sin
    personas visibles y se libera tras ``release_frames`` con al menos una
    persona visible.
    """

    def __init__(
        self,
        *,
        confirm_frames: int = DEFAULT_VACANCY_CONFIRM_FRAMES,
        release_frames: int = DEFAULT_VACANCY_RELEASE_FRAMES,
    ) -> None:
        if confirm_frames < 1:
            msg = f"La confirmacion requiere confirm_frames >= 1 (llego {confirm_frames})."
            raise ConfigError(msg)
        if release_frames < 1:
            msg = f"La liberacion requiere release_frames >= 1 (llego {release_frames})."
            raise ConfigError(msg)
        self._confirm_frames = confirm_frames
        self._release_frames = release_frames
        self._empty_frames = 0
        self._present_frames = 0
        self._active = False

    def update(self, tracked: tuple[TrackedDetection, ...]) -> VacancySnapshot:
        """Actualiza el estado con las detecciones del fotograma."""
        people_count = len(tracked)
        if people_count == 0:
            self._empty_frames += 1
            self._present_frames = 0
            if self._empty_frames >= self._confirm_frames:
                self._active = True
        else:
            self._present_frames += 1
            self._empty_frames = 0
            if self._present_frames >= self._release_frames:
                self._active = False
        return VacancySnapshot(active=self._active, people_count=people_count)

    def reset(self) -> None:
        """Limpia el estado del debounce."""
        self._empty_frames = 0
        self._present_frames = 0
        self._active = False
