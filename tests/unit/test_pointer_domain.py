"""Tests del dominio del puntero: calibracion de la zona activa a pantalla."""

import pytest

from recognizer.core.domain.hand import Point
from recognizer.core.domain.pointer import PointerCalibration, PointerPosition
from recognizer.core.errors import ConfigError

ZONE_MIN = 0.2
ZONE_MAX = 0.8
CENTER = 0.5


def _point(x: float, y: float) -> Point:
    return Point(x=x, y=y, z=0.0)


def _calibration(
    *,
    x_min: float = ZONE_MIN,
    x_max: float = ZONE_MAX,
    y_min: float = ZONE_MIN,
    y_max: float = ZONE_MAX,
    mirror_x: bool = True,
) -> PointerCalibration:
    return PointerCalibration(
        x_min=x_min,
        x_max=x_max,
        y_min=y_min,
        y_max=y_max,
        mirror_x=mirror_x,
    )


def test_map_mirrors_x_with_symmetric_zone() -> None:
    calibration = _calibration(mirror_x=True)

    left = calibration.map(_point(ZONE_MIN, ZONE_MIN))
    right = calibration.map(_point(ZONE_MAX, ZONE_MAX))

    assert left.x == pytest.approx(1.0)
    assert left.y == pytest.approx(0.0)
    assert right.x == pytest.approx(0.0)
    assert right.y == pytest.approx(1.0)


def test_map_without_mirror_keeps_x() -> None:
    calibration = _calibration(mirror_x=False)

    left = calibration.map(_point(ZONE_MIN, ZONE_MIN))
    right = calibration.map(_point(ZONE_MAX, ZONE_MAX))

    assert left.x == pytest.approx(0.0)
    assert right.x == pytest.approx(1.0)


def test_map_projects_y_axis_only() -> None:
    calibration = _calibration(mirror_x=False)

    bottom = calibration.map(_point(CENTER, ZONE_MIN))
    top = calibration.map(_point(CENTER, ZONE_MAX))

    assert bottom.y == pytest.approx(0.0)
    assert top.y == pytest.approx(1.0)
    assert bottom.x == pytest.approx(CENTER)
    assert top.x == pytest.approx(CENTER)


def test_map_clamps_points_outside_zone() -> None:
    calibration = _calibration(mirror_x=False)

    low = calibration.map(_point(0.0, 0.0))
    high = calibration.map(_point(1.0, 1.0))

    assert low == PointerPosition(x=0.0, y=0.0)
    assert high == PointerPosition(x=1.0, y=1.0)


def test_map_with_asymmetric_zone() -> None:
    calibration = _calibration(x_min=0.1, x_max=0.5, y_min=0.3, y_max=0.9, mirror_x=False)

    position = calibration.map(_point(0.3, 0.6))

    assert position.x == pytest.approx(0.5)
    assert position.y == pytest.approx(0.5)


@pytest.mark.parametrize("mirror_x", [True, False])
def test_map_center_is_exact_center(mirror_x: bool) -> None:
    calibration = _calibration(mirror_x=mirror_x)

    position = calibration.map(_point(CENTER, CENTER))

    assert position.x == pytest.approx(CENTER)
    assert position.y == pytest.approx(CENTER)


def test_valid_calibration_is_constructed() -> None:
    calibration = _calibration()

    assert calibration.x_min == ZONE_MIN
    assert calibration.x_max == ZONE_MAX
    assert calibration.y_min == ZONE_MIN
    assert calibration.y_max == ZONE_MAX
    assert calibration.mirror_x is True


@pytest.mark.parametrize(
    ("x_min", "x_max", "y_min", "y_max", "match"),
    [
        (CENTER, CENTER, ZONE_MIN, ZONE_MAX, "x_min < x_max"),
        (ZONE_MAX, ZONE_MIN, ZONE_MIN, ZONE_MAX, "x_min < x_max"),
        (ZONE_MIN, ZONE_MAX, CENTER, CENTER, "y_min < y_max"),
        (ZONE_MIN, ZONE_MAX, ZONE_MAX, ZONE_MIN, "y_min < y_max"),
    ],
)
def test_calibration_rejects_non_increasing_bounds(
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    match: str,
) -> None:
    with pytest.raises(ConfigError, match=match):
        _calibration(x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max)
