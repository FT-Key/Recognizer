"""Tests de deteccion de navegadores Chromium y resolucion de perfil."""

from pathlib import Path

from recognizer.adapters.chromium import (
    BrowserFamily,
    DetectedBrowser,
    autodetect_browser,
    resolve_profile_dir,
)


def test_autodetect_override_infers_chrome_family() -> None:
    result = autodetect_browser("C:\\chrome.exe")
    assert result is not None
    assert result.family == BrowserFamily.CHROME
    assert result.executable == "C:\\chrome.exe"


def test_autodetect_override_infers_brave_family() -> None:
    result = autodetect_browser("C:\\brave.exe")
    assert result is not None
    assert result.family == BrowserFamily.BRAVE


def test_autodetect_override_infers_edge_family() -> None:
    result = autodetect_browser("C:\\msedge.exe")
    assert result is not None
    assert result.family == BrowserFamily.EDGE


def test_autodetect_override_infers_opera_family() -> None:
    result = autodetect_browser("C:\\opera.exe")
    assert result is not None
    assert result.family == BrowserFamily.OPERA


def test_autodetect_override_infers_vivaldi_family() -> None:
    result = autodetect_browser("C:\\vivaldi.exe")
    assert result is not None
    assert result.family == BrowserFamily.VIVALDI


def test_autodetect_override_infers_chromium_family() -> None:
    result = autodetect_browser("C:\\chromium.exe")
    assert result is not None
    assert result.family == BrowserFamily.CHROMIUM


def test_autodetect_which_first_match() -> None:
    def fake_which(name: str) -> str | None:
        if name == "chromium":
            return "C:\\chromium.exe"
        return None

    result = autodetect_browser(_which=fake_which, _environ={}, _is_file=lambda _p: False)
    assert result is not None
    assert result.family == BrowserFamily.CHROMIUM
    assert result.executable == "C:\\chromium.exe"


def test_autodetect_env_paths_chrome() -> None:
    environ = {"LOCALAPPDATA": "C:\\Users\\X\\AppData\\Local"}

    def is_file(p: Path) -> bool:
        return "chrome.exe" in str(p).lower()

    result = autodetect_browser(_which=lambda _n: None, _environ=environ, _is_file=is_file)
    assert result is not None
    assert result.family == BrowserFamily.CHROME


def test_autodetect_returns_none_if_no_browser() -> None:
    result = autodetect_browser(
        _which=lambda _n: None,
        _environ={},
        _is_file=lambda _p: False,
    )
    assert result is None


def test_autodetect_env_edge_before_chrome_fails() -> None:
    environ = {"LOCALAPPDATA": "C:\\Users\\X\\AppData\\Local"}

    def is_file(_p: Path) -> bool:
        return False

    result = autodetect_browser(
        _which=lambda _n: None,
        _environ=environ,
        _is_file=is_file,
    )
    assert result is None


def test_resolve_profile_dir_includes_family() -> None:
    detected = DetectedBrowser(family=BrowserFamily.CHROME, executable="C:\\chrome.exe")
    result = resolve_profile_dir(detected, Path("base"))
    assert result == Path("base") / "browser-profile" / "chrome"


def test_resolve_profile_dir_brave() -> None:
    detected = DetectedBrowser(family=BrowserFamily.BRAVE, executable="C:\\brave.exe")
    result = resolve_profile_dir(detected, Path("base"))
    assert result == Path("base") / "browser-profile" / "brave"


def test_resolve_profile_dir_edge() -> None:
    detected = DetectedBrowser(family=BrowserFamily.EDGE, executable="C:\\msedge.exe")
    result = resolve_profile_dir(detected, Path("/opt"))
    assert result == Path("/opt") / "browser-profile" / "edge"


def test_autodetect_does_not_call_which_if_override_provided() -> None:
    which_called: list[str] = []

    def tracking_which(name: str) -> str | None:
        which_called.append(name)
        return "C:\\chromium.exe"

    result = autodetect_browser(
        "C:\\chrome.exe",
        _which=tracking_which,
        _environ={},
        _is_file=lambda _p: False,
    )
    assert result is not None
    assert result.family == BrowserFamily.CHROME
    assert which_called == []
