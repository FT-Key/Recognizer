"""Tests del dominio de loitering / zona permanencia (etapa 17a), sin hardware."""

import pytest

from recognizer.core.domain.detection import BoundingBox, Detection
from recognizer.core.domain.loitering import (
    LoiteringSnapshot,
    LoiteringZone,
    ZoneLoiteringMonitor,
)
from recognizer.core.domain.tracking import TrackedDetection
from recognizer.core.errors import ConfigError

ZONE = LoiteringZone(x_min=0.2, y_min=0.2, x_max=0.8, y_max=0.8)


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


# --- LoiteringZone ---


def test_zone_stores_rectangle() -> None:
    assert (ZONE.x_min, ZONE.y_min, ZONE.x_max, ZONE.y_max) == (0.2, 0.2, 0.8, 0.8)


@pytest.mark.parametrize("field", ["x_min", "y_min", "x_max", "y_max"])
@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_zone_rejects_out_of_range_coordinates(field: str, value: float) -> None:
    coords = {"x_min": 0.2, "y_min": 0.2, "x_max": 0.8, "y_max": 0.8}
    coords[field] = value

    with pytest.raises(ConfigError, match="0 <="):
        LoiteringZone(**coords)


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
        LoiteringZone(**coords)


def test_zone_contains_center_inside_and_outside() -> None:
    assert ZONE.contains(bbox=_inside_bbox())
    assert not ZONE.contains(bbox=_outside_bbox())


def test_zone_contains_is_inclusive_at_edges() -> None:
    assert ZONE.contains(bbox=_bbox(0.1, 0.1, 0.3, 0.3))
    assert ZONE.contains(bbox=_bbox(0.7, 0.7, 0.9, 0.9))


# --- ZoneLoiteringMonitor ---


def test_monitor_requires_confirm_frames_before_alerting() -> None:
    monitor = ZoneLoiteringMonitor(
        zone=ZONE,
        confirm_frames=2,
        release_frames=2,
        dwell_threshold_seconds=0.1,
    )
    inside = _tracked(1, bbox=_inside_bbox())

    first = monitor.update((inside,), fps=10.0)
    second = monitor.update((inside,), fps=10.0)

    assert first.active is False
    assert first.loiterer_ids == ()
    assert second.active is True
    assert second.loiterer_ids == (1,)
    assert second.count == 1


def test_monitor_never_confirms_track_outside_zone() -> None:
    monitor = ZoneLoiteringMonitor(
        zone=ZONE,
        confirm_frames=1,
        release_frames=1,
        dwell_threshold_seconds=0.1,
    )

    snapshot = monitor.update((_tracked(1, bbox=_outside_bbox()),), fps=10.0)

    assert snapshot.active is False
    assert snapshot.loiterer_ids == ()


def test_monitor_tracks_dwell_time_in_seconds() -> None:
    monitor = ZoneLoiteringMonitor(
        zone=ZONE,
        confirm_frames=1,
        release_frames=1,
        dwell_threshold_seconds=2.0,
    )
    inside = _tracked(1, bbox=_inside_bbox())

    first = monitor.update((inside,), fps=10.0)
    assert first.active is False
    assert first.dwell_times[1] == pytest.approx(0.1, abs=0.01)

    for _ in range(19):
        snapshot = monitor.update((inside,), fps=10.0)

    assert snapshot.active is True
    assert snapshot.dwell_times[1] == pytest.approx(2.0, abs=0.01)


def test_monitor_releases_loiterer_after_release_frames() -> None:
    monitor = ZoneLoiteringMonitor(
        zone=ZONE,
        confirm_frames=1,
        release_frames=2,
        dwell_threshold_seconds=0.1,
    )
    inside = _tracked(1, bbox=_inside_bbox())
    outside = _tracked(1, bbox=_outside_bbox())

    assert monitor.update((inside,), fps=10.0).active is True
    assert monitor.update((outside,), fps=10.0).active is False
    assert monitor.update((), fps=10.0).active is False


def test_monitor_releases_track_that_disappears() -> None:
    monitor = ZoneLoiteringMonitor(
        zone=ZONE,
        confirm_frames=1,
        release_frames=2,
        dwell_threshold_seconds=0.1,
    )

    assert monitor.update((_tracked(1, bbox=_inside_bbox()),), fps=10.0).active is True
    assert monitor.update((), fps=10.0).active is False
    assert monitor.update((), fps=10.0).active is False


def test_monitor_requires_reconfirm_after_release() -> None:
    monitor = ZoneLoiteringMonitor(
        zone=ZONE,
        confirm_frames=1,
        release_frames=1,
        dwell_threshold_seconds=0.1,
    )
    inside = _tracked(1, bbox=_inside_bbox())
    outside = _tracked(1, bbox=_outside_bbox())

    assert monitor.update((inside,), fps=10.0).active is True
    assert monitor.update((outside,), fps=10.0).active is False
    assert monitor.update((inside,), fps=10.0).active is True


def test_monitor_returns_sorted_loiterer_ids() -> None:
    monitor = ZoneLoiteringMonitor(
        zone=ZONE,
        confirm_frames=1,
        release_frames=1,
        dwell_threshold_seconds=0.1,
    )

    snapshot = monitor.update(
        (
            _tracked(5, bbox=_inside_bbox()),
            _tracked(2, bbox=_inside_bbox()),
            _tracked(9, bbox=_outside_bbox()),
        ),
        fps=10.0,
    )

    assert snapshot.loiterer_ids == (2, 5)
    assert snapshot.count == 2


def test_monitor_reset_clears_state() -> None:
    monitor = ZoneLoiteringMonitor(
        zone=ZONE,
        confirm_frames=1,
        release_frames=1,
        dwell_threshold_seconds=0.1,
    )
    assert monitor.update((_tracked(1, bbox=_inside_bbox()),), fps=10.0).active is True

    monitor.reset()

    assert monitor.update((), fps=10.0).active is False


@pytest.mark.parametrize("value", [0, -1])
def test_monitor_rejects_bad_confirm_frames(value: int) -> None:
    with pytest.raises(ConfigError, match="confirm_frames >= 1"):
        ZoneLoiteringMonitor(
            zone=ZONE,
            confirm_frames=value,
            release_frames=1,
            dwell_threshold_seconds=0.1,
        )


@pytest.mark.parametrize("value", [0, -1])
def test_monitor_rejects_bad_release_frames(value: int) -> None:
    with pytest.raises(ConfigError, match="release_frames >= 1"):
        ZoneLoiteringMonitor(
            zone=ZONE,
            confirm_frames=1,
            release_frames=value,
            dwell_threshold_seconds=0.1,
        )


@pytest.mark.parametrize("value", [0, -1])
def test_monitor_rejects_bad_dwell_threshold(value: float) -> None:
    with pytest.raises(ConfigError, match="dwell_threshold_seconds > 0"):
        ZoneLoiteringMonitor(
            zone=ZONE,
            confirm_frames=1,
            release_frames=1,
            dwell_threshold_seconds=value,
        )


def test_snapshot_count_matches_loiterer_ids() -> None:
    snapshot = LoiteringSnapshot(
        active=True,
        loiterer_ids=(1, 4, 7),
        dwell_times={},
    )

    assert snapshot.count == 3
    assert LoiteringSnapshot(active=False, loiterer_ids=(), dwell_times={}).count == 0
