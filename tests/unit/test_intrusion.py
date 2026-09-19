"""Tests del dominio de intrusion por zona (etapa 11), sin hardware."""

import pytest

from recognizer.core.domain.detection import BoundingBox, Detection
from recognizer.core.domain.intrusion import (
    IntrusionSnapshot,
    IntrusionZone,
    ZoneIntrusionMonitor,
)
from recognizer.core.domain.tracking import TrackedDetection
from recognizer.core.errors import ConfigError

ZONE = IntrusionZone(x_min=0.2, y_min=0.2, x_max=0.8, y_max=0.8)


def _bbox(
    x_min: float,
    y_min: float,
    x_max: float,
    y_max: float,
) -> BoundingBox:
    return BoundingBox(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)


def _inside_bbox() -> BoundingBox:
    return _bbox(0.4, 0.4, 0.6, 0.6)


def _outside_bbox() -> BoundingBox:
    return _bbox(0.0, 0.0, 0.1, 0.1)


def _tracked(track_id: int, *, bbox: BoundingBox) -> TrackedDetection:
    return TrackedDetection(
        track_id=track_id,
        detection=Detection(label="person", confidence=0.9, bbox=bbox),
    )


# --- IntrusionZone ---


def test_zone_stores_rectangle() -> None:
    assert (ZONE.x_min, ZONE.y_min, ZONE.x_max, ZONE.y_max) == (0.2, 0.2, 0.8, 0.8)


@pytest.mark.parametrize("field", ["x_min", "y_min", "x_max", "y_max"])
@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_zone_rejects_out_of_range_coordinates(field: str, value: float) -> None:
    coords = {"x_min": 0.2, "y_min": 0.2, "x_max": 0.8, "y_max": 0.8}
    coords[field] = value

    with pytest.raises(ConfigError, match="0 <="):
        IntrusionZone(**coords)


@pytest.mark.parametrize(
    "coords",
    [
        {"x_min": 0.5, "y_min": 0.2, "x_max": 0.5, "y_max": 0.8},
        {"x_min": 0.6, "y_min": 0.2, "x_max": 0.4, "y_max": 0.8},
        {"x_min": 0.2, "y_min": 0.5, "x_max": 0.8, "y_max": 0.5},
        {"x_min": 0.2, "y_min": 0.8, "x_max": 0.8, "y_max": 0.2},
    ],
)
def test_zone_rejects_degenerate_rectangles(coords: dict[str, float]) -> None:
    with pytest.raises(ConfigError, match=r"x_min < x_max|y_min < y_max"):
        IntrusionZone(**coords)


def test_zone_contains_center_inside_and_outside() -> None:
    assert ZONE.contains(bbox=_inside_bbox())
    assert not ZONE.contains(bbox=_outside_bbox())


def test_zone_contains_is_inclusive_at_edges() -> None:
    assert ZONE.contains(bbox=_bbox(0.1, 0.1, 0.3, 0.3))
    assert ZONE.contains(bbox=_bbox(0.7, 0.7, 0.9, 0.9))


# --- ZoneIntrusionMonitor ---


def test_monitor_requires_confirm_frames_before_alerting() -> None:
    monitor = ZoneIntrusionMonitor(zone=ZONE, confirm_frames=2, release_frames=2)
    inside = _tracked(1, bbox=_inside_bbox())

    first = monitor.update((inside,))
    second = monitor.update((inside,))

    assert first.active is False
    assert first.intruder_ids == ()
    assert second.active is True
    assert second.intruder_ids == (1,)
    assert second.count == 1


def test_monitor_never_confirms_track_outside_zone() -> None:
    monitor = ZoneIntrusionMonitor(zone=ZONE, confirm_frames=1, release_frames=1)

    snapshot = monitor.update((_tracked(1, bbox=_outside_bbox()),))

    assert snapshot.active is False
    assert snapshot.intruder_ids == ()


def test_monitor_releases_intruder_after_release_frames() -> None:
    monitor = ZoneIntrusionMonitor(zone=ZONE, confirm_frames=1, release_frames=2)
    outside = _tracked(1, bbox=_outside_bbox())

    assert monitor.update((_tracked(1, bbox=_inside_bbox()),)).active is True
    assert monitor.update((outside,)).active is True
    assert monitor.update((outside,)).active is False


def test_monitor_releases_track_that_disappears() -> None:
    monitor = ZoneIntrusionMonitor(zone=ZONE, confirm_frames=1, release_frames=2)

    assert monitor.update((_tracked(1, bbox=_inside_bbox()),)).active is True
    assert monitor.update(()).active is True
    assert monitor.update(()).active is False


def test_monitor_requires_reconfirm_after_release() -> None:
    monitor = ZoneIntrusionMonitor(zone=ZONE, confirm_frames=1, release_frames=1)
    inside = _tracked(1, bbox=_inside_bbox())
    outside = _tracked(1, bbox=_outside_bbox())

    assert monitor.update((inside,)).active is True
    assert monitor.update((outside,)).active is False
    assert monitor.update((inside,)).active is True


def test_monitor_returns_sorted_confirmed_intruders() -> None:
    monitor = ZoneIntrusionMonitor(zone=ZONE, confirm_frames=1, release_frames=1)

    snapshot = monitor.update(
        (
            _tracked(5, bbox=_inside_bbox()),
            _tracked(2, bbox=_inside_bbox()),
            _tracked(9, bbox=_outside_bbox()),
        )
    )

    assert snapshot.intruder_ids == (2, 5)
    assert snapshot.count == 2


def test_monitor_reset_clears_state() -> None:
    monitor = ZoneIntrusionMonitor(zone=ZONE, confirm_frames=1, release_frames=1)
    assert monitor.update((_tracked(1, bbox=_inside_bbox()),)).active is True

    monitor.reset()

    assert monitor.update(()).active is False


@pytest.mark.parametrize("value", [0, -1])
def test_monitor_rejects_bad_confirm_frames(value: int) -> None:
    with pytest.raises(ConfigError, match="confirm_frames >= 1"):
        ZoneIntrusionMonitor(zone=ZONE, confirm_frames=value, release_frames=1)


@pytest.mark.parametrize("value", [0, -1])
def test_monitor_rejects_bad_release_frames(value: int) -> None:
    with pytest.raises(ConfigError, match="release_frames >= 1"):
        ZoneIntrusionMonitor(zone=ZONE, confirm_frames=1, release_frames=value)


def test_snapshot_count_matches_intruder_ids() -> None:
    snapshot = IntrusionSnapshot(active=True, intruder_ids=(1, 4, 7))

    assert snapshot.count == 3
    assert IntrusionSnapshot(active=False, intruder_ids=()).count == 0
