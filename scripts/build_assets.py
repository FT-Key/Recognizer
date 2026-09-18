"""Genera los assets de escritorio (icono y logo) a partir del logo de la web.

Uso:
    uv run python scripts/build_assets.py

Fuente unica: ``web/public/minilogo.png`` (mismo icono que la pestana de la web).
Genera en ``assets/``:

    minilogo.png        copia del logo original
    minilogo.ico        icono multi-tamano para la barra de tareas / .exe
    minilogo-128.png    logo escalado para la cabecera del menu
    minilogo-64.png     logo escalado (favicon del .exe y avisos)

La tipografia pixel (Silkscreen, licencia OFL) ya vive versionada en ``assets/``;
este script no la descarga para que el build sea reproducible sin red.
"""

import shutil
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_LOGO = PROJECT_ROOT / "web" / "public" / "minilogo.png"
ASSETS_DIR = PROJECT_ROOT / "assets"

ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
HEADER_SIZE = 128
SMALL_SIZE = 64


def _load_source() -> Image.Image:
    """Carga el logo de la web o falla con un mensaje claro."""
    if not SOURCE_LOGO.is_file():
        msg = f"No existe el logo de origen: {SOURCE_LOGO}"
        raise SystemExit(msg)
    with Image.open(SOURCE_LOGO) as image:
        return image.convert("RGBA")


def _scaled(image: Image.Image, size: int) -> Image.Image:
    """Escala el logo a un cuadrado con remuestreo de alta calidad."""
    return image.resize((size, size), Image.Resampling.LANCZOS)


def main() -> int:
    """Regenera los assets de escritorio en ``assets/``."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    source = _load_source()

    shutil.copy2(SOURCE_LOGO, ASSETS_DIR / "minilogo.png")
    _scaled(source, HEADER_SIZE).save(ASSETS_DIR / "minilogo-128.png")
    _scaled(source, SMALL_SIZE).save(ASSETS_DIR / "minilogo-64.png")
    _scaled(source, max(ICON_SIZES)).save(
        ASSETS_DIR / "minilogo.ico",
        format="ICO",
        sizes=[(size, size) for size in ICON_SIZES],
    )

    print(f"Assets generados en: {ASSETS_DIR}")
    for name in ("minilogo.png", "minilogo.ico", "minilogo-128.png", "minilogo-64.png"):
        print(f"  - {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
