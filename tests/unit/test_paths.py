"""Tests de resolucion de rutas y assets del launcher, sin tocar el sistema."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from recognizer.cli import paths


def test_assets_dir_source_uses_repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths, "is_frozen", lambda: False)

    expected = Path(paths.__file__).resolve().parents[3] / paths.ASSETS_DIRNAME

    assert paths.assets_dir() == expected


def test_assets_dir_frozen_uses_meipass(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert paths.assets_dir() == tmp_path / paths.ASSETS_DIRNAME


def test_assets_dir_frozen_without_meipass_uses_executable_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)

    expected = Path(sys.executable).parent / paths.ASSETS_DIRNAME

    assert paths.assets_dir() == expected


def test_desktop_icon_path_returns_file_or_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(paths, "assets_dir", lambda: tmp_path)
    assert paths.desktop_icon_path() is None

    icon = tmp_path / paths.DESKTOP_ICON_FILENAME
    icon.write_bytes(b"ico")

    assert paths.desktop_icon_path() == icon


def test_desktop_logo_path_returns_file_or_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(paths, "assets_dir", lambda: tmp_path)
    assert paths.desktop_logo_path() is None

    logo = tmp_path / paths.DESKTOP_LOGO_FILENAME
    logo.write_bytes(b"png")

    assert paths.desktop_logo_path() == logo


def test_display_font_paths_lists_only_existing_fonts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(paths, "assets_dir", lambda: tmp_path)
    assert paths.display_font_paths() == ()

    regular_name, bold_name = paths.DISPLAY_FONT_FILENAMES
    regular = tmp_path / regular_name
    regular.write_bytes(b"ttf")

    assert paths.display_font_paths() == (regular,)

    bold = tmp_path / bold_name
    bold.write_bytes(b"ttf")

    assert paths.display_font_paths() == (regular, bold)
