"""Catalogo de aplicaciones del launcher multi-app.

Vocabulario puro del dominio: que aplicaciones existen, en que orden se muestran
y si estan implementadas. No conoce camara, modelos ni interfaz; el menu y los
runners viven en la capa `cli` (imperative shell).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from recognizer.core.errors import ConfigError


class AppId(StrEnum):
    """Identificador estable de cada aplicacion del launcher."""

    GESTURES = "gestures"
    PEOPLE_COUNTER = "people_counter"
    ANTI_INTRUDER = "anti_intruder"
    POSTURE = "posture"
    PPE_DETECTOR = "ppe_detector"
    INVENTORY = "inventory"
    FACE_AUTH = "face_auth"


class AppPreparation(StrEnum):
    """Trabajo previo que exige una app antes de poder implementarse."""

    TRAINING = "entrenamiento"
    ENROLLMENT = "enrolamiento"


class AppAvailability(StrEnum):
    """Estado de una app en el menu, derivado del catalogo y la configuracion."""

    AVAILABLE = "available"
    DISABLED = "disabled"
    COMING_SOON = "coming_soon"


@dataclass(frozen=True, slots=True)
class AppInfo:
    """Descripcion de una aplicacion y su estado de implementacion."""

    app_id: AppId
    title: str
    description: str
    implemented: bool = False
    preparation: AppPreparation | None = None


@dataclass(frozen=True, slots=True)
class AppRunRequest:
    """Opciones comunes con las que el launcher arranca cualquier aplicacion."""

    config_path: Path
    device: int | None = None
    max_frames: int = 0
    show_window: bool = True


# Orden pedido por el usuario: primero la app implementada, luego las que no
# requieren entrenamiento y al final las que si (entrenamiento o enrolamiento).
DEFAULT_APPS: tuple[AppInfo, ...] = (
    AppInfo(
        app_id=AppId.GESTURES,
        title="Reconocimiento de gestos",
        description="Controla el equipo con gestos de mano (MediaPipe).",
        implemented=True,
    ),
    AppInfo(
        app_id=AppId.PEOPLE_COUNTER,
        title="Contador de personas",
        description="Cuenta personas en camara con YOLO; no requiere entrenamiento.",
        implemented=True,
    ),
    AppInfo(
        app_id=AppId.ANTI_INTRUDER,
        title="Anti-intrusos",
        description="Detecta personas en una zona y dispara una alerta; no requiere entrenamiento.",
        implemented=True,
    ),
    AppInfo(
        app_id=AppId.POSTURE,
        title="Postura ergonomica",
        description="Avisa de mala postura con pose de cuerpo completo; no requiere entrenamiento.",
    ),
    AppInfo(
        app_id=AppId.PPE_DETECTOR,
        title="Detector EPP (obra)",
        description="Detecta casco y chaleco; requiere entrenar un modelo propio.",
        preparation=AppPreparation.TRAINING,
    ),
    AppInfo(
        app_id=AppId.INVENTORY,
        title="Inventario por camara",
        description="Registra objetos o productos por camara; requiere entrenar un modelo propio.",
        preparation=AppPreparation.TRAINING,
    ),
    AppInfo(
        app_id=AppId.FACE_AUTH,
        title="Reconocimiento facial",
        description="Registra tu cara y saluda al entrar; requiere enrolamiento, no entrenamiento.",
        preparation=AppPreparation.ENROLLMENT,
    ),
)


@dataclass(frozen=True, slots=True)
class AppCatalog:
    """Lista ordenada de aplicaciones y resolucion por id o numero de menu."""

    apps: tuple[AppInfo, ...] = DEFAULT_APPS

    def by_id(self, app_id: AppId) -> AppInfo | None:
        """Devuelve la app con ese id o ``None`` si no existe."""
        for info in self.apps:
            if info.app_id == app_id:
                return info
        return None

    def require(self, app_id: AppId) -> AppInfo:
        """Devuelve la app con ese id o falla con ``ConfigError``."""
        info = self.by_id(app_id)
        if info is None:
            msg = f"Aplicacion desconocida: {app_id}"
            raise ConfigError(msg)
        return info

    def by_number(self, number: int) -> AppInfo | None:
        """Resuelve una opcion 1-based del menu; ``None`` si esta fuera de rango."""
        if 1 <= number <= len(self.apps):
            return self.apps[number - 1]
        return None

    def availability(self, app_id: AppId, *, enabled: Mapping[AppId, bool]) -> AppAvailability:
        """Estado de la app combinando implementacion y habilitacion en config."""
        info = self.require(app_id)
        if not info.implemented:
            return AppAvailability.COMING_SOON
        if not enabled.get(app_id, True):
            return AppAvailability.DISABLED
        return AppAvailability.AVAILABLE
