"""Regiones de desenfoque para privacidad (dominio puro).

Convierte cajas faciales normalizadas en rectangulos de pixeles agrandados y
recortados al fotograma, y calcula el kernel gaussiano efectivo de cada uno.
Sin OpenCV ni numpy: el difuminado real vive en los adaptadores.
"""

from dataclasses import dataclass

from recognizer.core.constants import (
    DEFAULT_PRIVACY_FACE_MARGIN,
    MAX_BLUR_STRENGTH,
    MIN_BLUR_STRENGTH,
)
from recognizer.core.domain.face import FaceBox
from recognizer.core.errors import ConfigError

MIN_PIXEL_SIDE = 1


@dataclass(frozen=True, slots=True)
class PixelRect:
    """Rectangulo en pixeles del fotograma (x_min < x_max, y_min < y_max)."""

    x_min: int
    y_min: int
    x_max: int
    y_max: int

    def __post_init__(self) -> None:
        if self.x_min >= self.x_max:
            msg = "El rectangulo requiere x_min < x_max."
            raise ConfigError(msg)
        if self.y_min >= self.y_max:
            msg = "El rectangulo requiere y_min < y_max."
            raise ConfigError(msg)

    @property
    def width(self) -> int:
        """Ancho del rectangulo en pixeles."""
        return self.x_max - self.x_min

    @property
    def height(self) -> int:
        """Alto del rectangulo en pixeles."""
        return self.y_max - self.y_min


def _clamp_unit(value: float) -> float:
    """Recorta una coordenada normalizada al rango 0..1."""
    return max(0.0, min(1.0, value))


def face_blur_regions(
    boxes: tuple[FaceBox, ...],
    *,
    width: int,
    height: int,
    margin_ratio: float = DEFAULT_PRIVACY_FACE_MARGIN,
) -> tuple[PixelRect, ...]:
    """Rectangulos de pixeles a difuminar, agrandados y recortados.

    ``margin_ratio`` agranda cada caja en ambos ejes (cubre pelo y menton);
    las cajas degeneradas tras el recorte se descartan.

    Raises:
        ConfigError: si el fotograma o el margen son invalidos.
    """
    if width < MIN_PIXEL_SIDE or height < MIN_PIXEL_SIDE:
        msg = "El fotograma requiere ancho y alto positivos."
        raise ConfigError(msg)
    if margin_ratio < 0:
        msg = f"El margen requiere margin_ratio >= 0 (llego {margin_ratio})."
        raise ConfigError(msg)
    regions: list[PixelRect] = []
    for box in boxes:
        margin_x = box.width * margin_ratio
        margin_y = (box.y_max - box.y_min) * margin_ratio
        x_min = int(_clamp_unit(box.x_min - margin_x) * width)
        y_min = int(_clamp_unit(box.y_min - margin_y) * height)
        x_max = int(_clamp_unit(box.x_max + margin_x) * width)
        y_max = int(_clamp_unit(box.y_max + margin_y) * height)
        if x_max <= x_min or y_max <= y_min:
            continue
        regions.append(PixelRect(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max))
    return tuple(regions)


def effective_blur_kernel(*, strength: int, rect: PixelRect) -> int:
    """Kernel gaussiano impar util (0 = no difuminar).

    Se acota al lado menor del rectangulo para no difuminar con un kernel mas
    grande que la propia region; si el resultado queda por debajo del minimo,
    no se difumina.

    Raises:
        ConfigError: si ``strength`` esta fuera del rango permitido.
    """
    if not MIN_BLUR_STRENGTH <= strength <= MAX_BLUR_STRENGTH:
        msg = f"blur_strength requiere {MIN_BLUR_STRENGTH}..{MAX_BLUR_STRENGTH} (llego {strength})."
        raise ConfigError(msg)
    kernel = min(strength, rect.width, rect.height)
    if kernel % 2 == 0:
        kernel -= 1
    if kernel < MIN_BLUR_STRENGTH:
        return 0
    return kernel
