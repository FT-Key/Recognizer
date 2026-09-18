"""Tests de la configuracion de apps del launcher."""

import pytest
from pydantic import ValidationError

from recognizer.core.config import AppConfig, AppsConfig
from recognizer.core.domain.app import AppId


def test_apps_config_defaults_to_enabled() -> None:
    apps = AppsConfig()

    assert apps.enabled == {}
    assert apps.is_enabled(AppId.GESTURES) is True
    assert apps.is_enabled(AppId.PEOPLE_COUNTER) is True


def test_apps_config_reads_enabled_override() -> None:
    apps = AppsConfig.model_validate({"enabled": {"gestures": False}})

    assert apps.is_enabled(AppId.GESTURES) is False
    assert apps.is_enabled(AppId.PEOPLE_COUNTER) is True


def test_app_config_includes_apps_defaults() -> None:
    assert AppConfig().apps == AppsConfig()


def test_app_config_parses_apps_section() -> None:
    config = AppConfig.model_validate({"apps": {"enabled": {"gestures": False}}})

    assert config.apps.is_enabled(AppId.GESTURES) is False


def test_apps_config_rejects_unknown_app() -> None:
    with pytest.raises(ValidationError):
        AppsConfig.model_validate({"enabled": {"no_existe": True}})


def test_apps_config_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AppsConfig.model_validate({"otra": True})
