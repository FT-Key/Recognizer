"""Presentacion de arranque en consola: banner y progreso por etapas.

Solo usa `logging` (nunca `print`) para respetar la regla del proyecto. El banner
se emite como un unico mensaje multilinea precedido de un salto para que el
prefijo del formateador no rompa el marco.
"""

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from recognizer.cli.paths import LOG_DATE_FORMAT, LOG_FORMAT, resolve_log_file
from recognizer.core.constants import MILLISECONDS_PER_SECOND

BANNER_WIDTH = 62
BANNER_BORDER = "=" * BANNER_WIDTH
APP_TITLE = "R E C O G N I Z E R"
APP_TAGLINE = "reconocimiento de gestos por camara"
STEP_PREFIX = "  >>"
STEP_OK_PREFIX = "  OK"


def log_banner(logger: logging.Logger) -> None:
    """Registra el banner de arranque con el nombre de la aplicacion."""
    logger.info(
        "\n%s\n%s\n%s\n%s",
        BANNER_BORDER,
        APP_TITLE.center(BANNER_WIDTH),
        APP_TAGLINE.center(BANNER_WIDTH),
        BANNER_BORDER,
    )


def configure_logging(*, verbose: bool, log_file: Path | None) -> Path | None:
    """Configura logging a consola y, si se indica, a archivo. Devuelve el log usado."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    if log_file is None:
        return None

    resolved = resolve_log_file(log_file)
    handler = logging.FileHandler(resolved, encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    logging.getLogger().addHandler(handler)
    return resolved


@contextmanager
def log_step(logger: logging.Logger, message: str) -> Iterator[None]:
    """Anuncia una etapa de arranque y registra su duracion en milisegundos."""
    logger.info("%s %s...", STEP_PREFIX, message)
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * MILLISECONDS_PER_SECOND
        logger.info("%s %s (%.0f ms)", STEP_OK_PREFIX, message, elapsed_ms)
