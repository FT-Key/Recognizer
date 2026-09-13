"""Tests del catalogo abierto de gestos y del value object GestureId."""

import pytest

from recognizer.core.domain.gesture import (
    CANNED_GESTURE_LABELS,
    GESTURE_NONE,
    GESTURE_VICTORY,
    GestureCatalog,
    GestureId,
)
from recognizer.core.errors import ConfigError


def test_gesture_id_accepts_valid_label() -> None:
    gesture = GestureId("Victory")

    assert gesture.value == "Victory"
    assert str(gesture) == "Victory"


def test_gesture_id_equality_is_by_value() -> None:
    assert GestureId("Victory") == GestureId("Victory")
    assert GestureId("Victory") != GestureId("Open_Palm")


@pytest.mark.parametrize("label", ["", " Victory", "Victory ", "  "])
def test_gesture_id_rejects_invalid_labels(label: str) -> None:
    with pytest.raises(ConfigError, match="no es valido"):
        GestureId(label)


def test_empty_catalog_contains_canned_gestures() -> None:
    catalog = GestureCatalog.from_labels(custom_labels=(), rule_names=())

    for gesture in CANNED_GESTURE_LABELS:
        assert catalog.resolve(gesture) == GestureId(gesture)
    assert catalog.require(GESTURE_VICTORY.value) == GESTURE_VICTORY


def test_from_labels_includes_custom_and_rule_names() -> None:
    catalog = GestureCatalog.from_labels(
        custom_labels=("Custom_Wave",),
        rule_names=("L_Sign",),
    )

    assert catalog.resolve("Custom_Wave") == GestureId("Custom_Wave")
    assert catalog.resolve("L_Sign") == GestureId("L_Sign")
    assert catalog.is_known(GestureId("Custom_Wave"))
    assert catalog.is_known(GestureId("L_Sign"))


def test_from_labels_rejects_collision_with_canned_gesture() -> None:
    with pytest.raises(ConfigError, match="colisiona con un gesto predefinido"):
        GestureCatalog.from_labels(custom_labels=("Open_Palm",), rule_names=())


def test_from_labels_rejects_rule_named_none() -> None:
    with pytest.raises(ConfigError, match="colisiona con un gesto predefinido"):
        GestureCatalog.from_labels(custom_labels=(), rule_names=(GESTURE_NONE.value,))


def test_resolve_returns_none_for_unknown_label() -> None:
    catalog = GestureCatalog.from_labels(custom_labels=(), rule_names=())

    assert catalog.resolve("No_Existe") is None
    assert not catalog.is_known(GestureId("No_Existe"))


def test_require_raises_for_unknown_label() -> None:
    catalog = GestureCatalog.from_labels(custom_labels=(), rule_names=())

    with pytest.raises(ConfigError, match="Gesto desconocido"):
        catalog.require("No_Existe")


def test_labels_default_to_known_when_not_parsed() -> None:
    catalog = GestureCatalog(known=frozenset({GESTURE_VICTORY}))

    assert catalog.resolve("Victory") == GESTURE_VICTORY
    assert catalog.resolve("Open_Palm") is None
