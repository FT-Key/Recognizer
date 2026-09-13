"""Tests del dominio de manos: lateralidad, puntos y topologia."""

from dataclasses import FrozenInstanceError

import pytest

from recognizer.core.domain.hand import (
    HAND_CONNECTIONS,
    HAND_LANDMARK_COUNT,
    WRIST_LANDMARK_INDEX,
    Handedness,
    HandLandmarks,
    Point,
)

EXPECTED_CONNECTION_COUNT = 21


def test_handedness_values() -> None:
    assert Handedness.LEFT.value == "Left"
    assert Handedness.RIGHT.value == "Right"
    assert Handedness.UNKNOWN.value == "Unknown"
    assert {member.value for member in Handedness} == {"Left", "Right", "Unknown"}


def test_point_is_immutable() -> None:
    point = Point(x=0.1, y=0.2, z=0.3)
    with pytest.raises(FrozenInstanceError):
        point.__setattr__("x", 0.9)


def test_hand_landmarks_is_immutable() -> None:
    hand = HandLandmarks(handedness=Handedness.LEFT, confidence=0.8, points=())
    with pytest.raises(FrozenInstanceError):
        hand.__setattr__("confidence", 0.1)


def test_landmark_count_is_21() -> None:
    assert HAND_LANDMARK_COUNT == 21


def test_wrist_landmark_index_is_zero() -> None:
    assert WRIST_LANDMARK_INDEX == 0


def test_connections_use_valid_indices() -> None:
    for start, end in HAND_CONNECTIONS:
        assert start in range(HAND_LANDMARK_COUNT)
        assert end in range(HAND_LANDMARK_COUNT)
        assert start != end


def test_connections_have_no_duplicates() -> None:
    assert len(set(HAND_CONNECTIONS)) == len(HAND_CONNECTIONS)


def test_connections_match_official_topology_size() -> None:
    assert len(HAND_CONNECTIONS) == EXPECTED_CONNECTION_COUNT
