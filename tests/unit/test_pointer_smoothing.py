"""Tests del suavizado del puntero: Null Object, EMA y factory."""

from enum import StrEnum
from typing import cast

import pytest

from recognizer.core.domain.pointer import PointerPosition, SmoothingKind
from recognizer.core.errors import ConfigError
from recognizer.core.pointer.smoothing import (
    ExponentialSmoothing,
    NoSmoothing,
    create_smoothing,
)

ALPHA = 0.25
FIRST = PointerPosition(x=0.0, y=0.0)
SECOND = PointerPosition(x=1.0, y=0.5)
CONVERGENCE_SAMPLES = 100


class UnknownSmoothingKind(StrEnum):
    """Tipo de suavizado inexistente para cubrir el fallback de la factory."""

    GAUSSIAN = "gaussian"


def test_no_smoothing_returns_the_target() -> None:
    smoothing = NoSmoothing()
    target = PointerPosition(x=0.3, y=0.7)

    result = smoothing.smooth(target)

    assert result == target
    assert result is target


def test_no_smoothing_reset_keeps_working() -> None:
    smoothing = NoSmoothing()
    target = PointerPosition(x=0.3, y=0.7)
    smoothing.smooth(target)

    smoothing.reset()

    assert smoothing.smooth(target) == target


def test_ema_first_sample_returns_exact_target() -> None:
    smoothing = ExponentialSmoothing(alpha=ALPHA)
    target = PointerPosition(x=0.2, y=0.4)

    result = smoothing.smooth(target)

    assert result == target
    assert result is target


def test_ema_second_sample_blends_target_and_previous_per_axis() -> None:
    smoothing = ExponentialSmoothing(alpha=ALPHA)
    smoothing.smooth(FIRST)

    result = smoothing.smooth(SECOND)

    assert result.x == pytest.approx(0.25)
    assert result.y == pytest.approx(0.125)


def test_ema_converges_to_repeated_target() -> None:
    smoothing = ExponentialSmoothing(alpha=0.5)
    smoothing.smooth(FIRST)
    target = PointerPosition(x=0.9, y=0.1)

    result = target
    for _ in range(CONVERGENCE_SAMPLES):
        result = smoothing.smooth(target)

    assert result.x == pytest.approx(target.x)
    assert result.y == pytest.approx(target.y)


def test_ema_reset_restarts_state() -> None:
    smoothing = ExponentialSmoothing(alpha=ALPHA)
    smoothing.smooth(FIRST)

    smoothing.reset()
    result = smoothing.smooth(SECOND)

    assert result == SECOND
    assert result is SECOND


def test_create_smoothing_builds_no_smoothing() -> None:
    smoothing = create_smoothing(kind=SmoothingKind.NONE, alpha=ALPHA)

    assert isinstance(smoothing, NoSmoothing)


def test_create_smoothing_builds_exponential_smoothing() -> None:
    smoothing = create_smoothing(kind=SmoothingKind.EMA, alpha=ALPHA)

    assert isinstance(smoothing, ExponentialSmoothing)


def test_create_smoothing_rejects_unknown_kind() -> None:
    # cast documentado: tipo fuera del enum real para cubrir el fallback.
    unknown = cast(SmoothingKind, UnknownSmoothingKind.GAUSSIAN)

    with pytest.raises(ConfigError, match="Suavizado no soportado"):
        create_smoothing(kind=unknown, alpha=ALPHA)
