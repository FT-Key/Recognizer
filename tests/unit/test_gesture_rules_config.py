"""Tests de validacion de reglas de gestos y sus referencias en AppConfig."""

import pytest
from pydantic import ValidationError

from recognizer.core.config import (
    AngleConditionConfig,
    AppConfig,
    DirectionConditionConfig,
    GestureRuleConfig,
)
from recognizer.core.domain.gesture import (
    Direction8,
    Finger,
    GestureId,
    RulesPriority,
)


def test_rule_requires_at_least_one_condition() -> None:
    with pytest.raises(ValidationError, match="al menos una condicion"):
        GestureRuleConfig()


def test_rule_rejects_overlapping_extended_and_folded() -> None:
    with pytest.raises(ValidationError, match="extendido y doblado"):
        GestureRuleConfig(extended=(Finger.INDEX,), folded=(Finger.INDEX,))


@pytest.mark.parametrize(
    ("min_deg", "max_deg"),
    [
        (90.0, 90.0),
        (100.0, 90.0),
        (-1.0, 90.0),
        (0.0, 181.0),
    ],
)
def test_angle_condition_rejects_invalid_range(min_deg: float, max_deg: float) -> None:
    with pytest.raises(ValidationError, match="0 <= min_deg < max_deg <= 180"):
        AngleConditionConfig(
            a=Finger.THUMB,
            b=Finger.INDEX,
            min_deg=min_deg,
            max_deg=max_deg,
        )


def test_angle_condition_accepts_valid_range() -> None:
    condition = AngleConditionConfig(
        a=Finger.THUMB,
        b=Finger.INDEX,
        min_deg=50.0,
        max_deg=110.0,
    )

    assert condition.min_deg == 50.0
    assert condition.max_deg == 110.0


def test_rule_parses_direction_and_angle_conditions() -> None:
    rule = GestureRuleConfig.model_validate(
        {
            "extended": ["index"],
            "direction": {"finger": "index", "value": "up"},
            "angle": {"a": "thumb", "b": "index", "min_deg": 50, "max_deg": 110},
        }
    )

    assert rule.extended == (Finger.INDEX,)
    assert rule.direction == DirectionConditionConfig(finger=Finger.INDEX, value=Direction8.UP)
    assert rule.angle == AngleConditionConfig(
        a=Finger.THUMB,
        b=Finger.INDEX,
        min_deg=50.0,
        max_deg=110.0,
    )


def test_app_config_rejects_unknown_mapping_gesture() -> None:
    with pytest.raises(ValidationError, match="Gesto desconocido"):
        AppConfig.model_validate(
            {"actions": {"mappings": {"No_Existe": {"type": "media_key", "key": "volume_up"}}}}
        )


def test_app_config_rejects_unknown_activation_gesture() -> None:
    with pytest.raises(ValidationError, match="Gesto desconocido"):
        AppConfig.model_validate({"pointer": {"activation_gesture": "No_Existe"}})


def test_app_config_rejects_rule_colliding_with_canned_gesture() -> None:
    with pytest.raises(ValidationError, match="colisiona con un gesto predefinido"):
        AppConfig.model_validate({"gestures": {"rules": {"Open_Palm": {"extended": ["index"]}}}})


def test_app_config_accepts_declared_rules_and_custom_labels() -> None:
    config = AppConfig.model_validate(
        {
            "gestures": {
                "custom_labels": ["Custom_Wave"],
                "rules": {"L_Sign": {"extended": ["thumb"], "folded": ["middle"]}},
                "rules_priority": "model_first",
            },
            "actions": {
                "mappings": {
                    "L_Sign": {"type": "media_key", "key": "volume_up"},
                    "Custom_Wave": {"type": "hotkey", "keys": ["ctrl", "m"]},
                }
            },
            "pointer": {"activation_gesture": "L_Sign"},
        }
    )

    catalog = config.gesture_catalog()

    assert catalog.is_known(GestureId("L_Sign"))
    assert catalog.is_known(GestureId("Custom_Wave"))
    assert config.gestures.rules_priority is RulesPriority.MODEL_FIRST
    assert config.gestures.rules["L_Sign"].extended == (Finger.THUMB,)
