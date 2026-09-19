"""Deteccion de navegadores Chromium en el sistema."""

import logging
import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

LOGGER = logging.getLogger("recognizer.chromium")


class BrowserFamily(StrEnum):
    """Familia de navegadores basados en Chromium."""

    CHROME = "chrome"
    EDGE = "edge"
    BRAVE = "brave"
    VIVALDI = "vivaldi"
    OPERA = "opera"
    CHROMIUM = "chromium"


@dataclass(frozen=True)
class BrowserCandidate:
    """Candidato de navegador: nombre, variable de entorno y ruta relativa."""

    family: BrowserFamily
    name: str
    env: str | None
    relative_path: Path | None


BROWSER_CANDIDATES: tuple[BrowserCandidate, ...] = (
    BrowserCandidate(
        family=BrowserFamily.CHROME,
        name="chrome.exe",
        env="LOCALAPPDATA",
        relative_path=Path("Google") / "Chrome" / "Application" / "chrome.exe",
    ),
    BrowserCandidate(
        family=BrowserFamily.CHROME,
        name="chrome.exe",
        env="PROGRAMFILES",
        relative_path=Path("Google") / "Chrome" / "Application" / "chrome.exe",
    ),
    BrowserCandidate(
        family=BrowserFamily.CHROME,
        name="chrome.exe",
        env="PROGRAMFILES(X86)",
        relative_path=Path("Google") / "Chrome" / "Application" / "chrome.exe",
    ),
    BrowserCandidate(
        family=BrowserFamily.EDGE,
        name="msedge.exe",
        env="LOCALAPPDATA",
        relative_path=Path("Microsoft") / "Edge" / "Application" / "msedge.exe",
    ),
    BrowserCandidate(
        family=BrowserFamily.EDGE,
        name="msedge.exe",
        env="PROGRAMFILES",
        relative_path=Path("Microsoft") / "Edge" / "Application" / "msedge.exe",
    ),
    BrowserCandidate(
        family=BrowserFamily.EDGE,
        name="msedge.exe",
        env="PROGRAMFILES(X86)",
        relative_path=Path("Microsoft") / "Edge" / "Application" / "msedge.exe",
    ),
    BrowserCandidate(
        family=BrowserFamily.BRAVE,
        name="brave.exe",
        env="LOCALAPPDATA",
        relative_path=Path("BraveSoftware") / "Brave-Browser" / "Application" / "brave.exe",
    ),
    BrowserCandidate(
        family=BrowserFamily.BRAVE,
        name="brave.exe",
        env="PROGRAMFILES",
        relative_path=Path("BraveSoftware") / "Brave-Browser" / "Application" / "brave.exe",
    ),
    BrowserCandidate(
        family=BrowserFamily.VIVALDI,
        name="vivaldi.exe",
        env="LOCALAPPDATA",
        relative_path=Path("Vivaldi") / "Application" / "vivaldi.exe",
    ),
    BrowserCandidate(
        family=BrowserFamily.VIVALDI,
        name="vivaldi.exe",
        env="PROGRAMFILES",
        relative_path=Path("Vivaldi") / "Application" / "vivaldi.exe",
    ),
    BrowserCandidate(
        family=BrowserFamily.OPERA,
        name="opera.exe",
        env="LOCALAPPDATA",
        relative_path=Path("Programs") / "Opera" / "opera.exe",
    ),
    BrowserCandidate(
        family=BrowserFamily.OPERA,
        name="opera.exe",
        env="PROGRAMFILES",
        relative_path=Path("Opera") / "Application" / "opera.exe",
    ),
)

CHROMIUM_WHICH_NAMES: tuple[str, ...] = ("chromium", "chromium-browser")


@dataclass(frozen=True)
class DetectedBrowser:
    """Navegador detectado en el sistema."""

    family: BrowserFamily
    executable: str


def _family_from_filename(filename: str) -> BrowserFamily:
    """Infiere la familia del navegador a partir del nombre del ejecutable."""
    lower = filename.lower()
    if "chrome" in lower:
        return BrowserFamily.CHROME
    if "msedge" in lower:
        return BrowserFamily.EDGE
    if "brave" in lower:
        return BrowserFamily.BRAVE
    if "vivaldi" in lower:
        return BrowserFamily.VIVALDI
    if "opera" in lower:
        return BrowserFamily.OPERA
    if "chromium" in lower:
        return BrowserFamily.CHROMIUM
    msg = f"No se pudo inferir la familia del ejecutable: {filename}"
    raise ValueError(msg)


def autodetect_browser(
    executable_override: str | None = None,
    *,
    _which: Callable[[str], str | None] | None = None,
    _environ: Mapping[str, str] | None = None,
    _is_file: Callable[[Path], bool] | None = None,
) -> DetectedBrowser | None:
    """Detecta un navegador Chromium en el sistema.

    Si se proporciona ``executable_override``, se infiere la familia del nombre
    del archivo. En caso contrario, se buscan candidatos en orden:
    Chrome, Edge, Brave, Vivaldi, Opera, Chromium.
    """
    if _which is None:
        _which = shutil.which
    if _environ is None:
        import os

        _environ = os.environ
    if _is_file is None:
        _is_file = Path.is_file

    if executable_override is not None:
        filename = Path(executable_override).name
        family = _family_from_filename(filename)
        return DetectedBrowser(family=family, executable=executable_override)

    for candidate in BROWSER_CANDIDATES:
        if candidate.env is not None and candidate.relative_path is not None:
            root = _environ.get(candidate.env)
            if root:
                full_path = Path(root) / candidate.relative_path
                if _is_file(full_path):
                    return DetectedBrowser(
                        family=candidate.family,
                        executable=str(full_path),
                    )

    for name in CHROMIUM_WHICH_NAMES:
        found = _which(name)
        if found is not None:
            return DetectedBrowser(family=BrowserFamily.CHROMIUM, executable=found)

    return None


def resolve_profile_dir(detected: DetectedBrowser, base_dir: Path) -> Path:
    """Devuelve la ruta del perfil aislado para el navegador detectado."""
    return base_dir / "browser-profile" / detected.family.value
