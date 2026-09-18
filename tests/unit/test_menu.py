"""Tests del menu de aplicaciones (launcher), sin camara ni stdin real."""

import logging
from collections.abc import Callable
from pathlib import Path

import pytest

from recognizer.cli import menu
from recognizer.cli.menu import (
    LABEL_AVAILABLE,
    LABEL_COMING_SOON,
    LABEL_DISABLED,
    availability_label,
    render_catalog,
    resolve_runner,
    run_launcher,
    run_menu,
)
from recognizer.core.config import AppConfig, AppsConfig
from recognizer.core.domain.app import (
    AppAvailability,
    AppCatalog,
    AppId,
    AppInfo,
    AppPreparation,
    AppRunRequest,
)

REQUEST = AppRunRequest(config_path=Path("config.yaml"))
TEST_LOGGER = logging.getLogger("recognizer.menu.test")


def _scripted(values: list[str]) -> Callable[[str], str]:
    iterator = iter(values)

    def reader(_prompt: str) -> str:
        return next(iterator)

    return reader


def test_render_catalog_lists_apps_in_order_with_labels() -> None:
    text = render_catalog(AppCatalog(), AppsConfig())
    lines = text.splitlines()
    body = [line for line in lines if ") " in line and line.strip()[:1].isdigit()]

    assert body[0].startswith("  1) Reconocimiento de gestos")
    assert LABEL_AVAILABLE in body[0]
    assert body[1].startswith("  2) Contador de personas")
    assert LABEL_AVAILABLE in body[1]
    assert body[-1].strip() == "0) Salir"


def test_render_catalog_marks_training_requirement() -> None:
    text = render_catalog(AppCatalog(), AppsConfig())

    assert "requiere entrenamiento" in text
    assert "requiere enrolamiento" in text


def test_availability_label_variants() -> None:
    available = AppInfo(app_id=AppId.GESTURES, title="t", description="d", implemented=True)
    disabled = available
    coming = AppInfo(
        app_id=AppId.PPE_DETECTOR,
        title="t",
        description="d",
        preparation=AppPreparation.TRAINING,
    )

    assert availability_label(available, AppAvailability.AVAILABLE) == LABEL_AVAILABLE
    assert availability_label(disabled, AppAvailability.DISABLED) == LABEL_DISABLED
    assert (
        availability_label(coming, AppAvailability.COMING_SOON)
        == f"{LABEL_COMING_SOON} - requiere {AppPreparation.TRAINING.value}"
    )


def test_resolve_runner_returns_implemented_runners() -> None:
    from recognizer.cli.app import run_gestures
    from recognizer.cli.apps.people_counter import run_people_counter

    assert resolve_runner(AppId.GESTURES) is run_gestures
    assert resolve_runner(AppId.PEOPLE_COUNTER) is run_people_counter
    assert resolve_runner(AppId.ANTI_INTRUDER) is None


def test_run_menu_runs_selected_app_then_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[AppRunRequest] = []

    def fake_runner(request: AppRunRequest) -> int:
        calls.append(request)
        return 0

    monkeypatch.setattr(menu, "resolve_runner", lambda _app_id: fake_runner)

    result = run_menu(
        request=REQUEST,
        apps_config=AppsConfig(),
        input_fn=_scripted(["1", "0"]),
        logger=TEST_LOGGER,
    )

    assert result == 0
    assert calls == [REQUEST]


def test_run_menu_returns_to_menu_after_app(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def fake_runner(_request: AppRunRequest) -> int:
        calls.append(1)
        return 0

    monkeypatch.setattr(menu, "resolve_runner", lambda _app_id: fake_runner)

    run_menu(
        request=REQUEST,
        apps_config=AppsConfig(),
        input_fn=_scripted(["1", "1", "salir"]),
        logger=TEST_LOGGER,
    )

    assert len(calls) == 2


def test_run_menu_skips_coming_soon_without_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_resolve(_app_id: AppId) -> None:
        msg = "no debe resolverse un runner para una app no implementada"
        raise AssertionError(msg)

    monkeypatch.setattr(menu, "resolve_runner", fail_resolve)

    result = run_menu(
        request=REQUEST,
        apps_config=AppsConfig(),
        input_fn=_scripted(["3", "0"]),
        logger=TEST_LOGGER,
    )

    assert result == 0


def test_run_menu_skips_app_disabled_in_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def fake_runner(_request: AppRunRequest) -> int:
        calls.append(1)
        return 0

    monkeypatch.setattr(menu, "resolve_runner", lambda _app_id: fake_runner)

    run_menu(
        request=REQUEST,
        apps_config=AppsConfig(enabled={AppId.GESTURES: False}),
        input_fn=_scripted(["1", "0"]),
        logger=TEST_LOGGER,
    )

    assert calls == []


@pytest.mark.parametrize("invalid", ["abc", "99", "-1", ""])
def test_run_menu_rejects_invalid_choices(
    monkeypatch: pytest.MonkeyPatch,
    invalid: str,
) -> None:
    calls: list[int] = []

    def fake_runner(_request: AppRunRequest) -> int:
        calls.append(1)
        return 0

    monkeypatch.setattr(menu, "resolve_runner", lambda _app_id: fake_runner)

    result = run_menu(
        request=REQUEST,
        apps_config=AppsConfig(),
        input_fn=_scripted([invalid, "0"]),
        logger=TEST_LOGGER,
    )

    assert result == 0
    assert calls == []


def test_run_menu_returns_zero_on_eof() -> None:
    def eof(_prompt: str) -> str:
        raise EOFError

    assert (
        run_menu(
            request=REQUEST,
            apps_config=AppsConfig(),
            input_fn=eof,
            logger=TEST_LOGGER,
        )
        == 0
    )


def test_run_menu_returns_zero_on_keyboard_interrupt() -> None:
    def interrupt(_prompt: str) -> str:
        raise KeyboardInterrupt

    assert (
        run_menu(
            request=REQUEST,
            apps_config=AppsConfig(),
            input_fn=interrupt,
            logger=TEST_LOGGER,
        )
        == 0
    )


def test_run_menu_logs_error_when_runner_missing(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(menu, "resolve_runner", lambda _app_id: None)

    with caplog.at_level(logging.ERROR, logger=TEST_LOGGER.name):
        run_menu(
            request=REQUEST,
            apps_config=AppsConfig(),
            input_fn=_scripted(["1", "0"]),
            logger=TEST_LOGGER,
        )

    assert any("No hay runner" in record.getMessage() for record in caplog.records)


def test_run_launcher_list_only_does_not_open_menu(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(menu, "default_config_path", lambda: Path("config.yaml"))
    monkeypatch.setattr(menu, "load_config", lambda _path: AppConfig())

    def fail_menu(**_kwargs: object) -> int:
        msg = "list_only no debe abrir el menu interactivo"
        raise AssertionError(msg)

    monkeypatch.setattr(menu, "run_menu", fail_menu)

    with caplog.at_level(logging.INFO, logger=menu.LOGGER.name):
        result = run_launcher(list_only=True)

    assert result == 0
    assert any("Reconocimiento de gestos" in record.getMessage() for record in caplog.records)


def test_run_launcher_uses_default_config_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from recognizer.core.errors import ConfigError

    def failing_load(_path: Path) -> AppConfig:
        msg = "no existe"
        raise ConfigError(msg)

    captured: dict[str, object] = {}

    def fake_menu(**kwargs: object) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(menu, "default_config_path", lambda: Path("no-existe.yaml"))
    monkeypatch.setattr(menu, "load_config", failing_load)
    monkeypatch.setattr(menu, "run_menu", fake_menu)

    result = run_launcher()

    assert result == 0
    assert isinstance(captured["apps_config"], AppsConfig)
