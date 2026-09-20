"""Tests del dominio de vacancy / zona vacia (etapa 17b), sin hardware."""

import pytest

from recognizer.core.domain.detection import BoundingBox, Detection
from recognizer.core.domain.tracking import TrackedDetection
from recognizer.core.domain.vacancy import VacancyMonitor, VacancySnapshot
from recognizer.core.errors import ConfigError


def _bbox(
    x_min: float,
    y_min: float,
    x_max: float,
    y_max: float,
) -> BoundingBox:
    return BoundingBox(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)


def _tracked(track_id: int) -> TrackedDetection:
    return TrackedDetection(
        track_id=track_id,
        detection=Detection(
            label="person",
            confidence=0.9,
            bbox=_bbox(0.4, 0.4, 0.6, 0.6),
        ),
    )


# --- VacancyMonitor ---


@pytest.mark.parametrize("value", [0, -1])
def test_monitor_requires_confirm_frames(value: int) -> None:
    with pytest.raises(ConfigError, match="confirm_frames >= 1"):
        VacancyMonitor(confirm_frames=value, release_frames=1)


@pytest.mark.parametrize("value", [0, -1])
def test_monitor_requires_release_frames(value: int) -> None:
    with pytest.raises(ConfigError, match="release_frames >= 1"):
        VacancyMonitor(confirm_frames=1, release_frames=value)


def test_monitor_activates_after_empty_frames() -> None:
    monitor = VacancyMonitor(confirm_frames=3, release_frames=1)

    first = monitor.update(())
    second = monitor.update(())
    third = monitor.update(())

    assert first.active is False
    assert second.active is False
    assert third.active is True


def test_monitor_never_activates_with_people() -> None:
    monitor = VacancyMonitor(confirm_frames=2, release_frames=1)

    for _ in range(10):
        snapshot = monitor.update((_tracked(1),))

    assert snapshot.active is False


def test_monitor_releases_after_present_frames() -> None:
    monitor = VacancyMonitor(confirm_frames=1, release_frames=2)

    assert monitor.update(()).active is True
    assert monitor.update((_tracked(1),)).active is True
    assert monitor.update((_tracked(1),)).active is False


def test_monitor_releases_on_single_person_appearing() -> None:
    monitor = VacancyMonitor(confirm_frames=1, release_frames=1)

    assert monitor.update(()).active is True
    assert monitor.update((_tracked(1),)).active is False


def test_monitor_reset_clears_state() -> None:
    monitor = VacancyMonitor(confirm_frames=2, release_frames=1)
    assert monitor.update(()).active is False
    assert monitor.update(()).active is True

    monitor.reset()

    assert monitor.update(()).active is False


# --- VacancySnapshot ---


def test_snapshot_people_count() -> None:
    assert VacancySnapshot(active=True, people_count=0).people_count == 0
    assert VacancySnapshot(active=False, people_count=3).people_count == 3


def test_snapshot_active_is_boolean() -> None:
    assert isinstance(VacancySnapshot(active=True, people_count=0).active, bool)
    assert isinstance(VacancySnapshot(active=False, people_count=1).active, bool)
