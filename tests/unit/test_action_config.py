"""Tests de la configuracion de acciones locales y del config.yaml real."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from recognizer.core.config import (
    ActionsConfig,
    AppConfig,
    CommandActionConfig,
    GestureConfig,
    HotkeyActionConfig,
    MediaKeyActionConfig,
    MenuConfig,
    OpenLinksActionConfig,
    ScriptActionConfig,
)
from recognizer.core.constants import DEFAULT_ACTION_COOLDOWN_SECONDS
from recognizer.core.domain.action import MediaKey, ScriptInterpreter
from recognizer.core.domain.hand import Handedness
from recognizer.settings import load_config

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config.yaml"


def test_actions_config_defaults() -> None:
    config = ActionsConfig()

    assert config.cooldown_seconds == DEFAULT_ACTION_COOLDOWN_SECONDS
    assert config.mappings == {}
    assert config.menus == {}


def test_gesture_swap_handedness_defaults_false() -> None:
    assert GestureConfig().swap_handedness is False
    assert GestureConfig(swap_handedness=True).swap_handedness is True


def test_menu_config_parses_valid_options() -> None:
    menu = MenuConfig.model_validate(
        {
            "hand": "Left",
            "modifier": "Pointing_Up",
            "consume_trigger": False,
            "options": {"Victory": {"type": "hotkey", "keys": ["ctrl", "m"]}},
        }
    )

    assert menu.hand is Handedness.LEFT
    assert menu.modifier == "Pointing_Up"
    assert menu.consume_trigger is False
    assert isinstance(menu.options["Victory"], HotkeyActionConfig)


@pytest.mark.parametrize(
    "menu",
    [
        {"hand": "Left", "modifier": "Pointing_Up"},
        {"hand": "Left", "modifier": "Pointing_Up", "options": {}},
        {
            "hand": "Left",
            "modifier": "",
            "options": {"Victory": {"type": "hotkey", "keys": ["ctrl"]}},
        },
        {
            "hand": "Sideways",
            "modifier": "Pointing_Up",
            "options": {"Victory": {"type": "hotkey", "keys": ["ctrl"]}},
        },
    ],
)
def test_invalid_menu_config_is_rejected(menu: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        MenuConfig.model_validate(menu)


def test_actions_config_accepts_menus() -> None:
    config = ActionsConfig.model_validate(
        {
            "menus": {
                "Replay": {
                    "hand": "Left",
                    "modifier": "Pointing_Up",
                    "options": {"Victory": {"type": "hotkey", "keys": ["ctrl"]}},
                }
            }
        }
    )

    assert set(config.menus) == {"Replay"}


def test_app_config_accepts_menu_with_known_gestures() -> None:
    config = AppConfig.model_validate(
        {
            "actions": {
                "menus": {
                    "Replay": {
                        "hand": "Left",
                        "modifier": "Pointing_Up",
                        "options": {"Victory": {"type": "hotkey", "keys": ["ctrl", "m"]}},
                    }
                }
            }
        }
    )

    assert "Replay" in config.actions.menus


@pytest.mark.parametrize(
    "menu",
    [
        {
            "hand": "Left",
            "modifier": "NoExiste",
            "options": {"Victory": {"type": "hotkey", "keys": ["ctrl"]}},
        },
        {
            "hand": "Left",
            "modifier": "Pointing_Up",
            "options": {"NoExiste": {"type": "hotkey", "keys": ["ctrl"]}},
        },
    ],
)
def test_app_config_rejects_unknown_menu_gestures(menu: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="Gesto desconocido"):
        AppConfig.model_validate({"actions": {"menus": {"Replay": menu}}})


def test_media_key_mapping_parses() -> None:
    config = ActionsConfig.model_validate(
        {"mappings": {"Thumb_Up": {"type": "media_key", "key": "volume_up"}}}
    )

    action = config.mappings["Thumb_Up"]
    assert isinstance(action, MediaKeyActionConfig)
    assert action.key is MediaKey.VOLUME_UP


def test_hotkey_mapping_parses() -> None:
    config = ActionsConfig.model_validate(
        {"mappings": {"Victory": {"type": "hotkey", "keys": ["ctrl", "shift", "m"]}}}
    )

    action = config.mappings["Victory"]
    assert isinstance(action, HotkeyActionConfig)
    assert action.keys == ("ctrl", "shift", "m")


def test_command_mapping_parses() -> None:
    config = ActionsConfig.model_validate(
        {"mappings": {"ILoveYou": {"type": "command", "argv": ["notepad.exe", "notas.txt"]}}}
    )

    action = config.mappings["ILoveYou"]
    assert isinstance(action, CommandActionConfig)
    assert action.argv == ("notepad.exe", "notas.txt")


def test_script_mapping_parses_with_defaults() -> None:
    config = ActionsConfig.model_validate(
        {"mappings": {"Victory": {"type": "script", "path": "scripts/celebrate.py"}}}
    )

    action = config.mappings["Victory"]
    assert isinstance(action, ScriptActionConfig)
    assert action.path == "scripts/celebrate.py"
    assert action.args == ()
    assert action.interpreter is ScriptInterpreter.AUTO
    assert action.working_dir is None
    assert action.blocking is False
    assert action.timeout_seconds == 0.0
    assert action.pass_context is False


def test_script_mapping_parses_with_optionals() -> None:
    config = ActionsConfig.model_validate(
        {
            "mappings": {
                "Victory": {
                    "type": "script",
                    "path": "scripts/celebrate.ps1",
                    "args": ["--loud"],
                    "interpreter": "powershell",
                    "working_dir": "scripts",
                    "blocking": True,
                    "timeout_seconds": 2.5,
                    "pass_context": True,
                }
            }
        }
    )

    action = config.mappings["Victory"]
    assert isinstance(action, ScriptActionConfig)
    assert action.args == ("--loud",)
    assert action.interpreter is ScriptInterpreter.POWERSHELL
    assert action.working_dir == "scripts"
    assert action.blocking is True
    assert action.timeout_seconds == 2.5
    assert action.pass_context is True


@pytest.mark.parametrize(
    "mapping",
    [
        {"type": "script"},
        {"type": "script", "path": "script.py", "timeout_seconds": -0.1},
        {"type": "script", "path": "script.py", "interpreter": "ruby"},
        {"type": "script", "path": "script.py", "blocking": True},
    ],
)
def test_invalid_script_mapping_is_rejected(mapping: object) -> None:
    with pytest.raises(ValidationError):
        ActionsConfig.model_validate({"mappings": {"Victory": mapping}})


def test_open_links_mapping_parses_single_url_with_defaults() -> None:
    config = ActionsConfig.model_validate(
        {"mappings": {"ILoveYou": {"type": "open_links", "urls": ["https://unico.example"]}}}
    )

    action = config.mappings["ILoveYou"]
    assert isinstance(action, OpenLinksActionConfig)
    assert action.urls == ("https://unico.example",)
    assert action.browser is None


def test_open_links_mapping_parses_multiple_urls_and_browser() -> None:
    config = ActionsConfig.model_validate(
        {
            "mappings": {
                "ILoveYou": {
                    "type": "open_links",
                    "urls": ["http://primero.example", "https://segundo.example"],
                    "browser": "C:\\chrome.exe",
                }
            }
        }
    )

    action = config.mappings["ILoveYou"]
    assert isinstance(action, OpenLinksActionConfig)
    assert action.urls == ("http://primero.example", "https://segundo.example")
    assert action.browser == "C:\\chrome.exe"


@pytest.mark.parametrize(
    "mapping",
    [
        {"type": "open_links"},
        {"type": "open_links", "urls": []},
        {"type": "open_links", "urls": ["ftp://archivo.example"]},
        {"type": "open_links", "urls": ["sin-esquema.example"]},
        {"type": "open_links", "urls": ["https://ok.example"], "browser": 5},
    ],
)
def test_invalid_open_links_mapping_is_rejected(mapping: object) -> None:
    with pytest.raises(ValidationError):
        ActionsConfig.model_validate({"mappings": {"ILoveYou": mapping}})


def test_unknown_action_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ActionsConfig.model_validate({"mappings": {"Thumb_Up": {"type": "noop"}}})


def test_unknown_media_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ActionsConfig.model_validate(
            {"mappings": {"Thumb_Up": {"type": "media_key", "key": "no_existe"}}}
        )


def test_action_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ActionsConfig.model_validate(
            {"mappings": {"Thumb_Up": {"type": "media_key", "key": "volume_up", "extra": True}}}
        )


def test_actions_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ActionsConfig.model_validate({"desconocido": True})


@pytest.mark.parametrize("gesture_key", ["None", None])
def test_none_gesture_mapping_is_rejected(gesture_key: object) -> None:
    with pytest.raises(ValidationError):
        ActionsConfig.model_validate(
            {"mappings": {gesture_key: {"type": "media_key", "key": "volume_up"}}}
        )


@pytest.mark.parametrize("cooldown", [-0.1, -1.0])
def test_negative_cooldown_is_rejected(cooldown: float) -> None:
    with pytest.raises(ValidationError):
        ActionsConfig.model_validate({"cooldown_seconds": cooldown})


def test_empty_cooldown_is_allowed() -> None:
    assert ActionsConfig.model_validate({"cooldown_seconds": 0}).cooldown_seconds == 0


@pytest.mark.parametrize(
    "mapping",
    [
        {"type": "hotkey", "keys": []},
        {"type": "command", "argv": []},
    ],
)
def test_empty_keys_and_argv_are_rejected(mapping: object) -> None:
    with pytest.raises(ValidationError):
        ActionsConfig.model_validate({"mappings": {"Victory": mapping}})


def test_repo_config_loads_expected_mappings() -> None:
    app_config = load_config(CONFIG_PATH)
    mappings = app_config.actions.mappings

    assert set(mappings) == {
        "Thumb_Up",
        "Thumb_Down",
        "Closed_Fist",
        "Open_Palm",
        "Victory",
        "ILoveYou",
    }
    assert mappings["Thumb_Up"] == MediaKeyActionConfig(key=MediaKey.VOLUME_UP)
    assert mappings["Thumb_Down"] == MediaKeyActionConfig(key=MediaKey.VOLUME_DOWN)
    assert mappings["Closed_Fist"] == MediaKeyActionConfig(key=MediaKey.VOLUME_MUTE)
    assert mappings["Open_Palm"] == MediaKeyActionConfig(key=MediaKey.PLAY_PAUSE)
    assert mappings["Victory"] == HotkeyActionConfig(keys=("ctrl", "shift", "m"))
    assert mappings["ILoveYou"] == OpenLinksActionConfig(
        urls=("https://www.youtube.com/watch?v=mlabBbn_fHI&t=0s",)
    )


def test_repo_config_loads_replay_menu() -> None:
    app_config = load_config(CONFIG_PATH)
    menu = app_config.actions.menus["Replay"]

    assert menu.hand is Handedness.LEFT
    assert menu.modifier == "Pointing_Up"
    assert menu.consume_trigger is True
    assert set(menu.options) == {"Victory"}
    assert isinstance(menu.options["Victory"], ScriptActionConfig)
    assert app_config.gestures.swap_handedness is False
