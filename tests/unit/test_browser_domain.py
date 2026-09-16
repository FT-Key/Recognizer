"""Tests de los objetos de valor del dominio del navegador."""

import pytest

from recognizer.core.domain.browser import TabKey, TabSpec
from recognizer.core.errors import ConfigError


def test_tab_key_rejects_whitespace_padded() -> None:
    with pytest.raises(ConfigError, match="identificador de pestana no es valido"):
        TabKey("  video  ")


def test_tab_key_empty_raises() -> None:
    with pytest.raises(ConfigError, match="identificador de pestana no es valido"):
        TabKey("")


def test_tab_key_whitespace_only_raises() -> None:
    with pytest.raises(ConfigError, match="identificador de pestana no es valido"):
        TabKey("   ")


def test_tab_key_strips_and_rejects_leading_trailing_spaces() -> None:
    with pytest.raises(ConfigError, match="identificador de pestana no es valido"):
        TabKey(" video ")


def test_tab_key_str() -> None:
    assert str(TabKey("video")) == "video"


def test_tab_key_is_hashable() -> None:
    key = TabKey("v")
    assert {key, TabKey("v")} == {key}


def test_tab_spec_creation() -> None:
    spec = TabSpec(
        key=TabKey("v"),
        url="https://x.example",
        match="x.example",
    )
    assert spec.key == TabKey("v")
    assert spec.url == "https://x.example"
    assert spec.match == "x.example"


def test_tab_spec_frozen() -> None:
    spec = TabSpec(
        key=TabKey("v"),
        url="https://x.example",
        match="x.example",
    )
    with pytest.raises(AttributeError):
        spec.url = "https://y.example"  # type: ignore[misc]
