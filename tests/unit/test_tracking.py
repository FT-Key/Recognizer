"""Tests del tracking de objetos y del conteo de cruces de linea (etapa 10c).

Cubre el dominio puro: ``BoundingBox``, ``TrackedDetection``, ``CountingLine`` y
``LineCrossingCounter``, ademas de la configuracion de la linea de conteo.
"""

import pytest
from pydantic import ValidationError

from recognizer.core.config import AppConfig, CountingLineConfig, PeopleCounterConfig
from recognizer.core.constants import (
    DEFAULT_LINE_CONFIRM_FRAMES,
    DEFAULT_LINE_POSITION,
    PERSON_LABEL,
)
from recognizer.core.domain.detection import BoundingBox, Detection
from recognizer.core.domain.tracking import (
    SIDE_NEGATIVE,
    SIDE_POSITIVE,
    CountingLine,
    LineAxis,
    LineCrossingCounter,
    TrackedDetection,
)
from recognizer.core.errors import ConfigError

LINE_POSITION = 0.5
TRACK_ID = 7


def _bbox(*, x_min: float, y_min: float, x_max: float, y_max: float) -> BoundingBox:
    return BoundingBox(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)


def _above() -> BoundingBox:
    """Caja con centro en Y = 0.2 (lado negativo de una linea horizontal en 0.5)."""
    return _bbox(x_min=0.4, y_min=0.1, x_max=0.6, y_max=0.3)


def _below() -> BoundingBox:
    """Caja con centro en Y = 0.8 (lado positivo de una linea horizontal en 0.5)."""
    return _bbox(x_min=0.4, y_min=0.7, x_max=0.6, y_max=0.9)


def _left() -> BoundingBox:
    """Caja con centro en X = 0.2 (lado negativo de una linea vertical en 0.5)."""
    return _bbox(x_min=0.1, y_min=0.4, x_max=0.3, y_max=0.6)


def _right() -> BoundingBox:
    """Caja con centro en X = 0.8 (lado positivo de una linea vertical en 0.5)."""
    return _bbox(x_min=0.7, y_min=0.4, x_max=0.9, y_max=0.6)


def _detection(
    *,
    bbox: BoundingBox | None = None,
    label: str = PERSON_LABEL,
    confidence: float = 0.9,
) -> Detection:
    return Detection(label=label, confidence=confidence, bbox=bbox or _above())


def _tracked(track_id: int = TRACK_ID, *, bbox: BoundingBox | None = None) -> TrackedDetection:
    return TrackedDetection(track_id=track_id, detection=_detection(bbox=bbox))


def _horizontal() -> CountingLine:
    return CountingLine(axis=LineAxis.HORIZONTAL, position=LINE_POSITION)


def _counter(*, invert: bool = False, confirm_frames: int = 1) -> LineCrossingCounter:
    return LineCrossingCounter(line=_horizontal(), invert=invert, confirm_frames=confirm_frames)


# --- BoundingBox: centro ---


def test_bbox_center_returns_midpoint() -> None:
    box = _bbox(x_min=0.1, y_min=0.2, x_max=0.4, y_max=0.8)

    assert box.center_x == pytest.approx(0.25)
    assert box.center_y == pytest.approx(0.5)


# --- TrackedDetection ---


def test_tracked_detection_delegates_to_detection() -> None:
    detection = _detection(label="car", confidence=0.75)
    tracked = TrackedDetection(track_id=TRACK_ID, detection=detection)

    assert tracked.track_id == TRACK_ID
    assert tracked.label == detection.label
    assert tracked.confidence == detection.confidence
    assert tracked.bbox == detection.bbox


def test_tracked_detection_rejects_negative_track_id() -> None:
    with pytest.raises(ConfigError, match="track_id >= 0"):
        TrackedDetection(track_id=-1, detection=_detection())


# --- CountingLine ---


@pytest.mark.parametrize("position", [-0.1, 0.0, 1.0, 1.1])
def test_counting_line_rejects_position_out_of_range(position: float) -> None:
    with pytest.raises(ConfigError, match="0 < position < 1"):
        CountingLine(axis=LineAxis.HORIZONTAL, position=position)


def test_counting_line_horizontal_uses_center_y() -> None:
    line = _horizontal()

    assert line.coordinate(bbox=_above()) == pytest.approx(0.2)
    assert line.coordinate(bbox=_below()) == pytest.approx(0.8)


def test_counting_line_vertical_uses_center_x() -> None:
    line = CountingLine(axis=LineAxis.VERTICAL, position=LINE_POSITION)

    assert line.coordinate(bbox=_left()) == pytest.approx(0.2)
    assert line.coordinate(bbox=_right()) == pytest.approx(0.8)


def test_counting_line_side_is_positive_over_the_line() -> None:
    horizontal = _horizontal()
    vertical = CountingLine(axis=LineAxis.VERTICAL, position=LINE_POSITION)

    assert horizontal.side(bbox=_below()) == SIDE_POSITIVE
    assert horizontal.side(bbox=_above()) == SIDE_NEGATIVE
    assert vertical.side(bbox=_right()) == SIDE_POSITIVE
    assert vertical.side(bbox=_left()) == SIDE_NEGATIVE


def test_counting_line_center_on_line_counts_as_negative_side() -> None:
    on_line = _bbox(x_min=0.4, y_min=0.4, x_max=0.6, y_max=0.6)

    assert _horizontal().side(bbox=on_line) == SIDE_NEGATIVE


# --- LineCrossingCounter ---


def test_counter_new_track_does_not_count() -> None:
    counter = _counter()

    snapshot = counter.update((_tracked(bbox=_above()),))

    assert (snapshot.entries, snapshot.exits) == (0, 0)
    assert (counter.entries, counter.exits) == (0, 0)


def test_counter_negative_to_positive_counts_entry() -> None:
    counter = _counter()
    counter.update((_tracked(bbox=_above()),))

    snapshot = counter.update((_tracked(bbox=_below()),))

    assert (snapshot.entries, snapshot.exits) == (1, 0)


def test_counter_positive_to_negative_counts_exit() -> None:
    counter = _counter()
    counter.update((_tracked(bbox=_below()),))

    snapshot = counter.update((_tracked(bbox=_above()),))

    assert (snapshot.entries, snapshot.exits) == (0, 1)


def test_counter_invert_swaps_entry_and_exit() -> None:
    counter = _counter(invert=True)
    counter.update((_tracked(bbox=_above()),))

    snapshot = counter.update((_tracked(bbox=_below()),))

    assert (snapshot.entries, snapshot.exits) == (0, 1)


def test_counter_debounce_ignores_transient_side_change() -> None:
    counter = _counter(confirm_frames=3)
    counter.update((_tracked(bbox=_above()),))
    counter.update((_tracked(bbox=_below()),))

    snapshot = counter.update((_tracked(bbox=_above()),))

    assert (snapshot.entries, snapshot.exits) == (0, 0)


def test_counter_debounce_counts_when_side_holds_confirm_frames() -> None:
    counter = _counter(confirm_frames=3)
    counter.update((_tracked(bbox=_above()),))
    counter.update((_tracked(bbox=_below()),))
    counter.update((_tracked(bbox=_below()),))
    assert counter.entries == 0

    snapshot = counter.update((_tracked(bbox=_below()),))

    assert (snapshot.entries, snapshot.exits) == (1, 0)


def test_counter_tracks_are_independent() -> None:
    counter = _counter()
    counter.update((_tracked(1, bbox=_above()), _tracked(2, bbox=_above())))

    snapshot = counter.update((_tracked(1, bbox=_below()), _tracked(2, bbox=_above())))
    assert snapshot.entries == 1

    snapshot = counter.update((_tracked(2, bbox=_below()),))
    assert snapshot.entries == 2


def test_counter_reset_clears_counters_and_state() -> None:
    counter = _counter()
    counter.update((_tracked(bbox=_above()),))
    counter.update((_tracked(bbox=_below()),))
    assert counter.entries == 1

    counter.reset()

    assert (counter.entries, counter.exits) == (0, 0)
    snapshot = counter.update((_tracked(bbox=_below()),))
    assert (snapshot.entries, snapshot.exits) == (0, 0)
    snapshot = counter.update((_tracked(bbox=_above()),))
    assert (snapshot.entries, snapshot.exits) == (0, 1)


@pytest.mark.parametrize("confirm_frames", [0, -1])
def test_counter_rejects_non_positive_confirm_frames(confirm_frames: int) -> None:
    with pytest.raises(ConfigError, match="confirm_frames >= 1"):
        _counter(confirm_frames=confirm_frames)


# --- Configuracion de la linea ---


def test_counting_line_config_defaults() -> None:
    config = CountingLineConfig()

    assert config.enabled is True
    assert config.axis is LineAxis.HORIZONTAL
    assert config.position == DEFAULT_LINE_POSITION
    assert config.invert is False
    assert config.confirm_frames == DEFAULT_LINE_CONFIRM_FRAMES


@pytest.mark.parametrize("position", [-0.1, 0.0, 1.0, 1.1])
def test_counting_line_config_rejects_position_out_of_range(position: float) -> None:
    with pytest.raises(ValidationError):
        CountingLineConfig(position=position)


def test_counting_line_config_rejects_zero_confirm_frames() -> None:
    with pytest.raises(ValidationError):
        CountingLineConfig(confirm_frames=0)


def test_people_counter_config_includes_line() -> None:
    assert PeopleCounterConfig().line == CountingLineConfig()


def test_app_config_parses_people_counter_line() -> None:
    parsed = AppConfig.model_validate(
        {
            "people_counter": {
                "line": {
                    "axis": "vertical",
                    "position": 0.25,
                    "invert": True,
                    "confirm_frames": 3,
                }
            }
        }
    )

    assert parsed.people_counter.line.axis is LineAxis.VERTICAL
    assert parsed.people_counter.line.position == 0.25
    assert parsed.people_counter.line.invert is True
    assert parsed.people_counter.line.confirm_frames == 3
