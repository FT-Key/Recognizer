"""Tests del tracking de objetos y del conteo de cruces de linea (etapa 10c).

Cubre el dominio puro: ``BoundingBox``, ``TrackedDetection``, ``CountingLine`` y
``LineCrossingCounter``, ademas de la configuracion de la linea de conteo.
"""

import pytest
from pydantic import ValidationError

from recognizer.core.config import AppConfig, CountingLineConfig, PeopleCounterConfig
from recognizer.core.constants import (
    DEFAULT_LINE_CONFIRM_FRAMES,
    DEFAULT_LINE_MARGIN,
    DEFAULT_LINE_POSITION,
    DEFAULT_TRACK_TIMEOUT_FRAMES,
    PERSON_LABEL,
)
from recognizer.core.domain.detection import BoundingBox, Detection
from recognizer.core.domain.tracking import (
    SIDE_NEGATIVE,
    SIDE_POSITIVE,
    SIDE_UNKNOWN,
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


def _in_band() -> BoundingBox:
    """Caja con centro en Y = 0.5, dentro de la banda muerta de la linea."""
    return _bbox(x_min=0.4, y_min=0.4, x_max=0.6, y_max=0.6)


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


def _counter(
    *,
    invert: bool = False,
    confirm_frames: int = 1,
    track_timeout_frames: int = DEFAULT_TRACK_TIMEOUT_FRAMES,
) -> LineCrossingCounter:
    return LineCrossingCounter(
        line=_horizontal(),
        invert=invert,
        confirm_frames=confirm_frames,
        track_timeout_frames=track_timeout_frames,
    )


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


def test_counting_line_zone_is_positive_over_the_line() -> None:
    horizontal = _horizontal()
    vertical = CountingLine(axis=LineAxis.VERTICAL, position=LINE_POSITION)

    assert horizontal.zone(bbox=_below()) == SIDE_POSITIVE
    assert horizontal.zone(bbox=_above()) == SIDE_NEGATIVE
    assert vertical.zone(bbox=_right()) == SIDE_POSITIVE
    assert vertical.zone(bbox=_left()) == SIDE_NEGATIVE


def test_counting_line_center_on_line_is_unknown() -> None:
    on_line = _bbox(x_min=0.4, y_min=0.4, x_max=0.6, y_max=0.6)

    assert _horizontal().zone(bbox=on_line) == SIDE_UNKNOWN


@pytest.mark.parametrize(
    ("center_y", "expected"),
    [
        (0.39, SIDE_NEGATIVE),
        (0.40, SIDE_UNKNOWN),
        (0.45, SIDE_UNKNOWN),
        (0.50, SIDE_UNKNOWN),
        (0.55, SIDE_UNKNOWN),
        (0.60, SIDE_UNKNOWN),
        (0.61, SIDE_POSITIVE),
    ],
)
def test_counting_line_horizontal_zone_respects_margin_band(
    center_y: float,
    expected: int,
) -> None:
    line = CountingLine(axis=LineAxis.HORIZONTAL, position=LINE_POSITION, margin=0.1)
    bbox = _bbox(x_min=0.4, y_min=center_y - 0.01, x_max=0.6, y_max=center_y + 0.01)

    assert line.zone(bbox=bbox) == expected


def test_counting_line_vertical_zone_respects_margin_band() -> None:
    line = CountingLine(axis=LineAxis.VERTICAL, position=LINE_POSITION, margin=0.1)
    inside = _bbox(x_min=0.5, y_min=0.4, x_max=0.6, y_max=0.6)
    outside = _bbox(x_min=0.6, y_min=0.4, x_max=0.62, y_max=0.6)

    assert line.zone(bbox=inside) == SIDE_UNKNOWN
    assert line.zone(bbox=outside) == SIDE_POSITIVE


@pytest.mark.parametrize("margin", [-0.1, -0.01])
def test_counting_line_rejects_negative_margin(margin: float) -> None:
    with pytest.raises(ConfigError, match="margin"):
        CountingLine(axis=LineAxis.HORIZONTAL, position=LINE_POSITION, margin=margin)


@pytest.mark.parametrize(
    ("position", "margin"),
    [(0.5, 0.5), (0.2, 0.2), (0.8, 0.2), (0.2, 0.9)],
)
def test_counting_line_rejects_margin_too_large(position: float, margin: float) -> None:
    with pytest.raises(ConfigError, match="margin"):
        CountingLine(axis=LineAxis.HORIZONTAL, position=position, margin=margin)


# --- LineCrossingCounter ---


def test_counter_new_track_does_not_count() -> None:
    counter = _counter()

    snapshot = counter.update((_tracked(bbox=_above()),))

    assert (snapshot.entries, snapshot.exits) == (0, 0)
    assert (counter.entries, counter.exits) == (0, 0)


def test_counter_track_born_in_band_sets_side_without_counting() -> None:
    counter = _counter()

    first = counter.update((_tracked(bbox=_in_band()),))
    second = counter.update((_tracked(bbox=_below()),))

    assert (first.entries, first.exits) == (0, 0)
    assert (second.entries, second.exits) == (0, 0)

    snapshot = counter.update((_tracked(bbox=_above()),))
    assert (snapshot.entries, snapshot.exits) == (0, 1)


def test_counter_jitter_inside_band_does_not_change_side_or_count() -> None:
    counter = _counter()
    counter.update((_tracked(bbox=_above()),))

    for _ in range(3):
        snapshot = counter.update((_tracked(bbox=_in_band()),))

    assert (snapshot.entries, snapshot.exits) == (0, 0)
    snapshot = counter.update((_tracked(bbox=_below()),))
    assert (snapshot.entries, snapshot.exits) == (1, 0)


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


def test_counter_purges_track_after_timeout_frames() -> None:
    counter = _counter(track_timeout_frames=2)
    counter.update((_tracked(bbox=_above()),))

    counter.update(())
    counter.update(())

    snapshot = counter.update((_tracked(bbox=_below()),))

    assert (snapshot.entries, snapshot.exits) == (0, 0)


def test_counter_track_survives_within_timeout_frames() -> None:
    counter = _counter(track_timeout_frames=3)
    counter.update((_tracked(bbox=_above()),))

    counter.update(())
    counter.update(())

    snapshot = counter.update((_tracked(bbox=_below()),))

    assert (snapshot.entries, snapshot.exits) == (1, 0)


@pytest.mark.parametrize("confirm_frames", [0, -1])
def test_counter_rejects_non_positive_confirm_frames(confirm_frames: int) -> None:
    with pytest.raises(ConfigError, match="confirm_frames >= 1"):
        _counter(confirm_frames=confirm_frames)


@pytest.mark.parametrize("track_timeout_frames", [0, -1])
def test_counter_rejects_non_positive_track_timeout(track_timeout_frames: int) -> None:
    with pytest.raises(ConfigError, match="track_timeout_frames >= 1"):
        _counter(track_timeout_frames=track_timeout_frames)


# --- Configuracion de la linea ---


def test_counting_line_config_defaults() -> None:
    config = CountingLineConfig()

    assert config.enabled is True
    assert config.axis is LineAxis.VERTICAL
    assert config.position == DEFAULT_LINE_POSITION
    assert config.margin == DEFAULT_LINE_MARGIN
    assert config.invert is False
    assert config.confirm_frames == DEFAULT_LINE_CONFIRM_FRAMES
    assert config.track_timeout_frames == DEFAULT_TRACK_TIMEOUT_FRAMES


@pytest.mark.parametrize("position", [-0.1, 0.0, 1.0, 1.1])
def test_counting_line_config_rejects_position_out_of_range(position: float) -> None:
    with pytest.raises(ValidationError):
        CountingLineConfig(position=position)


def test_counting_line_config_rejects_zero_confirm_frames() -> None:
    with pytest.raises(ValidationError):
        CountingLineConfig(confirm_frames=0)


@pytest.mark.parametrize("margin", [-0.1, 0.5, 0.6])
def test_counting_line_config_rejects_bad_margin(margin: float) -> None:
    with pytest.raises(ValidationError):
        CountingLineConfig(margin=margin)


@pytest.mark.parametrize("track_timeout_frames", [0, -1])
def test_counting_line_config_rejects_non_positive_track_timeout(
    track_timeout_frames: int,
) -> None:
    with pytest.raises(ValidationError):
        CountingLineConfig(track_timeout_frames=track_timeout_frames)


def test_people_counter_config_includes_line() -> None:
    assert PeopleCounterConfig().line == CountingLineConfig()


def test_app_config_parses_people_counter_line() -> None:
    parsed = AppConfig.model_validate(
        {
            "people_counter": {
                "line": {
                    "axis": "vertical",
                    "position": 0.25,
                    "margin": 0.1,
                    "invert": True,
                    "confirm_frames": 3,
                    "track_timeout_frames": 12,
                }
            }
        }
    )

    assert parsed.people_counter.line.axis is LineAxis.VERTICAL
    assert parsed.people_counter.line.position == 0.25
    assert parsed.people_counter.line.margin == 0.1
    assert parsed.people_counter.line.invert is True
    assert parsed.people_counter.line.confirm_frames == 3
    assert parsed.people_counter.line.track_timeout_frames == 12
