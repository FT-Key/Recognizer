"""Tests del motor de reglas geometricas de gestos sobre landmarks sinteticos."""

import math
from collections.abc import Sequence

import numpy as np
import pytest
from numpy.typing import NDArray

from recognizer.core.config import (
    AngleConditionConfig,
    DirectionConditionConfig,
    GestureRuleConfig,
    RuleThresholdsConfig,
)
from recognizer.core.constants import RULE_CONFIDENCE
from recognizer.core.domain.frame import Frame
from recognizer.core.domain.gesture import (
    GESTURE_NONE,
    GESTURE_OPEN_PALM,
    GESTURE_VICTORY,
    DetectedGesture,
    Direction8,
    Finger,
    GestureId,
    RulesPriority,
)
from recognizer.core.domain.hand import (
    HAND_LANDMARK_COUNT,
    INDEX_FINGER_MCP_LANDMARK_INDEX,
    INDEX_FINGER_PIP_LANDMARK_INDEX,
    INDEX_FINGER_TIP_LANDMARK_INDEX,
    MIDDLE_FINGER_MCP_LANDMARK_INDEX,
    MIDDLE_FINGER_PIP_LANDMARK_INDEX,
    MIDDLE_FINGER_TIP_LANDMARK_INDEX,
    PINKY_MCP_LANDMARK_INDEX,
    PINKY_PIP_LANDMARK_INDEX,
    PINKY_TIP_LANDMARK_INDEX,
    RING_FINGER_MCP_LANDMARK_INDEX,
    RING_FINGER_PIP_LANDMARK_INDEX,
    RING_FINGER_TIP_LANDMARK_INDEX,
    THUMB_IP_LANDMARK_INDEX,
    THUMB_MCP_LANDMARK_INDEX,
    THUMB_TIP_LANDMARK_INDEX,
    Handedness,
    HandLandmarks,
    Point,
)
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.pipeline.landmark_rules import (
    LandmarkRule,
    LandmarkRuleProcessor,
    evaluate_rule,
    finger_direction,
    is_finger_extended,
    match_rules,
    matches_angle,
    matches_direction,
)

STRAIGHT_ANGLE_DEG = 160.0
DIRECTION_TOLERANCE_DEG = 30.0
HALF_TOLERANCE_DEG = 45.0
FINGER_LENGTH = 0.2
CENTER = 0.5
FRAME_SHAPE = (4, 6, 3)
HAND_CONFIDENCE = 0.9
DETECTION_CONFIDENCE = 0.8

THRESHOLDS = RuleThresholdsConfig(
    straight_angle_deg=STRAIGHT_ANGLE_DEG,
    direction_tolerance_deg=DIRECTION_TOLERANCE_DEG,
)

# Triple (MCP, PIP/IP, TIP) por dedo, igual que la topologia de MediaPipe.
_FINGER_ANGLE_INDEX: dict[Finger, tuple[int, int, int]] = {
    Finger.THUMB: (
        THUMB_MCP_LANDMARK_INDEX,
        THUMB_IP_LANDMARK_INDEX,
        THUMB_TIP_LANDMARK_INDEX,
    ),
    Finger.INDEX: (
        INDEX_FINGER_MCP_LANDMARK_INDEX,
        INDEX_FINGER_PIP_LANDMARK_INDEX,
        INDEX_FINGER_TIP_LANDMARK_INDEX,
    ),
    Finger.MIDDLE: (
        MIDDLE_FINGER_MCP_LANDMARK_INDEX,
        MIDDLE_FINGER_PIP_LANDMARK_INDEX,
        MIDDLE_FINGER_TIP_LANDMARK_INDEX,
    ),
    Finger.RING: (
        RING_FINGER_MCP_LANDMARK_INDEX,
        RING_FINGER_PIP_LANDMARK_INDEX,
        RING_FINGER_TIP_LANDMARK_INDEX,
    ),
    Finger.PINKY: (
        PINKY_MCP_LANDMARK_INDEX,
        PINKY_PIP_LANDMARK_INDEX,
        PINKY_TIP_LANDMARK_INDEX,
    ),
}

# El eje y crece hacia abajo: "arriba" es negativo y "abajo" positivo.
_DIRECTION_VECTORS: dict[Direction8, tuple[float, float]] = {
    Direction8.UP: (0.0, -1.0),
    Direction8.DOWN: (0.0, 1.0),
    Direction8.LEFT: (-1.0, 0.0),
    Direction8.RIGHT: (1.0, 0.0),
    Direction8.UP_LEFT: (-1.0, -1.0),
    Direction8.UP_RIGHT: (1.0, -1.0),
    Direction8.DOWN_LEFT: (-1.0, 1.0),
    Direction8.DOWN_RIGHT: (1.0, 1.0),
}


def _base_points() -> list[Point]:
    return [Point(x=CENTER, y=CENTER, z=0.0) for _ in range(HAND_LANDMARK_COUNT)]


def _unit(dx: float, dy: float) -> tuple[float, float]:
    norm = math.hypot(dx, dy)
    return dx / norm, dy / norm


def _place_finger(
    points: list[Point],
    finger: Finger,
    direction: Direction8,
    *,
    bent: bool = False,
) -> None:
    """Coloca un dedo apuntando a ``direction``; si ``bent``, lo flexiona 90 grados."""
    mcp, vertex, tip = _FINGER_ANGLE_INDEX[finger]
    unit_x, unit_y = _unit(*_DIRECTION_VECTORS[direction])
    points[mcp] = Point(x=CENTER - unit_x * FINGER_LENGTH, y=CENTER - unit_y * FINGER_LENGTH, z=0.0)
    points[vertex] = Point(x=CENTER, y=CENTER, z=0.0)
    tip_x, tip_y = (-unit_y, unit_x) if bent else (unit_x, unit_y)
    points[tip] = Point(x=CENTER + tip_x * FINGER_LENGTH, y=CENTER + tip_y * FINGER_LENGTH, z=0.0)


def _hand(
    *,
    points: Sequence[Point] | None = None,
    handedness: Handedness = Handedness.RIGHT,
) -> HandLandmarks:
    return HandLandmarks(
        handedness=handedness,
        confidence=HAND_CONFIDENCE,
        points=tuple(points) if points is not None else tuple(_base_points()),
    )


def _frame() -> Frame:
    data: NDArray[np.uint8] = np.zeros(FRAME_SHAPE, dtype=np.uint8)
    return Frame(data=data, timestamp=0.0)


def _detection(name: GestureId = GESTURE_OPEN_PALM) -> DetectedGesture:
    return DetectedGesture(
        name=name,
        confidence=DETECTION_CONFIDENCE,
        handedness=Handedness.RIGHT,
    )


def _rule(
    gesture: GestureId = GESTURE_VICTORY,
    *,
    config: GestureRuleConfig,
) -> LandmarkRule:
    return LandmarkRule(gesture=gesture, config=config)


def test_is_finger_extended_and_folded() -> None:
    straight = _base_points()
    _place_finger(straight, Finger.INDEX, Direction8.UP)

    bent = _base_points()
    _place_finger(bent, Finger.INDEX, Direction8.UP, bent=True)

    assert is_finger_extended(
        points=straight,
        finger=Finger.INDEX,
        straight_angle_deg=STRAIGHT_ANGLE_DEG,
    )
    assert not is_finger_extended(
        points=bent,
        finger=Finger.INDEX,
        straight_angle_deg=STRAIGHT_ANGLE_DEG,
    )


@pytest.mark.parametrize("direction", list(Direction8))
def test_finger_direction_classifies_every_sector(direction: Direction8) -> None:
    points = _base_points()
    _place_finger(points, Finger.INDEX, direction)

    assert finger_direction(points=points, finger=Finger.INDEX) is direction


def test_matches_direction_with_tolerance() -> None:
    points = _base_points()
    _place_finger(points, Finger.INDEX, Direction8.UP_RIGHT)
    up = DirectionConditionConfig(finger=Finger.INDEX, value=Direction8.UP)

    assert matches_direction(points=points, condition=up, tolerance_deg=HALF_TOLERANCE_DEG)
    assert not matches_direction(points=points, condition=up, tolerance_deg=DIRECTION_TOLERANCE_DEG)


def test_matches_direction_rejects_opposite_direction() -> None:
    points = _base_points()
    _place_finger(points, Finger.INDEX, Direction8.UP)
    down = DirectionConditionConfig(finger=Finger.INDEX, value=Direction8.DOWN)

    assert not matches_direction(
        points=points, condition=down, tolerance_deg=DIRECTION_TOLERANCE_DEG
    )


def test_matches_angle_within_and_out_of_range() -> None:
    points = _base_points()
    _place_finger(points, Finger.INDEX, Direction8.UP)
    _place_finger(points, Finger.MIDDLE, Direction8.RIGHT)
    inside = AngleConditionConfig(
        a=Finger.INDEX,
        b=Finger.MIDDLE,
        min_deg=80.0,
        max_deg=100.0,
    )
    outside = AngleConditionConfig(
        a=Finger.INDEX,
        b=Finger.MIDDLE,
        min_deg=100.0,
        max_deg=120.0,
    )

    assert matches_angle(points=points, condition=inside)
    assert not matches_angle(points=points, condition=outside)


def test_evaluate_rule_requires_all_conditions() -> None:
    rule = _rule(
        config=GestureRuleConfig(
            extended=(Finger.INDEX,),
            folded=(Finger.MIDDLE,),
        )
    )
    valid = _base_points()
    _place_finger(valid, Finger.INDEX, Direction8.UP)
    _place_finger(valid, Finger.MIDDLE, Direction8.DOWN, bent=True)

    middle_also_straight = _base_points()
    _place_finger(middle_also_straight, Finger.INDEX, Direction8.UP)
    _place_finger(middle_also_straight, Finger.MIDDLE, Direction8.DOWN)

    assert evaluate_rule(points=valid, rule=rule, thresholds=THRESHOLDS)
    assert not evaluate_rule(points=middle_also_straight, rule=rule, thresholds=THRESHOLDS)


def test_evaluate_rule_rejects_wrong_point_count() -> None:
    rule = _rule(config=GestureRuleConfig(extended=(Finger.INDEX,)))
    points = _base_points()[:5]

    assert not evaluate_rule(points=points, rule=rule, thresholds=THRESHOLDS)


def test_evaluate_rule_combines_direction_and_angle() -> None:
    rule = _rule(
        config=GestureRuleConfig(
            direction=DirectionConditionConfig(finger=Finger.INDEX, value=Direction8.UP),
            angle=AngleConditionConfig(
                a=Finger.INDEX,
                b=Finger.MIDDLE,
                min_deg=80.0,
                max_deg=100.0,
            ),
        )
    )
    valid = _base_points()
    _place_finger(valid, Finger.INDEX, Direction8.UP)
    _place_finger(valid, Finger.MIDDLE, Direction8.RIGHT)
    wrong_angle = _base_points()
    _place_finger(wrong_angle, Finger.INDEX, Direction8.UP)
    _place_finger(wrong_angle, Finger.MIDDLE, Direction8.UP)
    wrong_direction = _base_points()
    _place_finger(wrong_direction, Finger.INDEX, Direction8.DOWN)
    _place_finger(wrong_direction, Finger.MIDDLE, Direction8.RIGHT)

    assert evaluate_rule(points=valid, rule=rule, thresholds=THRESHOLDS)
    assert not evaluate_rule(points=wrong_angle, rule=rule, thresholds=THRESHOLDS)
    assert not evaluate_rule(points=wrong_direction, rule=rule, thresholds=THRESHOLDS)


def test_match_rules_returns_first_match_or_none() -> None:
    first = _rule(GESTURE_VICTORY, config=GestureRuleConfig(extended=(Finger.INDEX,)))
    second = _rule(GESTURE_OPEN_PALM, config=GestureRuleConfig(extended=(Finger.INDEX,)))
    points = _base_points()
    _place_finger(points, Finger.INDEX, Direction8.UP)

    assert match_rules(points=points, rules=(first, second), thresholds=THRESHOLDS) is first
    assert match_rules(points=_base_points(), rules=(first, second), thresholds=THRESHOLDS) is None


def test_processor_rules_first_prefers_rule() -> None:
    rule = _rule(config=GestureRuleConfig(extended=(Finger.INDEX,)))
    points = _base_points()
    _place_finger(points, Finger.INDEX, Direction8.UP)
    processor = LandmarkRuleProcessor(
        rules=(rule,),
        thresholds=THRESHOLDS,
        priority=RulesPriority.RULES_FIRST,
    )
    context = FrameContext(
        frame=_frame(),
        hands=(_hand(points=points),),
        detections=(_detection(GESTURE_OPEN_PALM),),
    )

    result = processor.process(context)

    assert result.detections[0].name == GESTURE_VICTORY
    assert result.detections[0].confidence == RULE_CONFIDENCE
    assert result.detections[0].handedness is Handedness.RIGHT


def test_processor_rules_first_falls_back_to_model_then_none() -> None:
    rule = _rule(config=GestureRuleConfig(extended=(Finger.INDEX,)))
    processor = LandmarkRuleProcessor(
        rules=(rule,),
        thresholds=THRESHOLDS,
        priority=RulesPriority.RULES_FIRST,
    )

    with_model = processor.process(
        FrameContext(
            frame=_frame(),
            hands=(_hand(),),
            detections=(_detection(GESTURE_OPEN_PALM),),
        )
    )
    without_model = processor.process(FrameContext(frame=_frame(), hands=(_hand(),)))

    assert with_model.detections[0].name == GESTURE_OPEN_PALM
    assert without_model.detections[0].name is GESTURE_NONE
    assert without_model.detections[0].confidence == 0.0


def test_processor_model_first_prefers_non_none_model() -> None:
    rule = _rule(config=GestureRuleConfig(extended=(Finger.INDEX,)))
    points = _base_points()
    _place_finger(points, Finger.INDEX, Direction8.UP)
    processor = LandmarkRuleProcessor(
        rules=(rule,),
        thresholds=THRESHOLDS,
        priority=RulesPriority.MODEL_FIRST,
    )
    context = FrameContext(
        frame=_frame(),
        hands=(_hand(points=points),),
        detections=(_detection(GESTURE_OPEN_PALM),),
    )

    result = processor.process(context)

    assert result.detections[0].name == GESTURE_OPEN_PALM


def test_processor_model_first_uses_rule_when_model_is_none() -> None:
    rule = _rule(config=GestureRuleConfig(extended=(Finger.INDEX,)))
    points = _base_points()
    _place_finger(points, Finger.INDEX, Direction8.UP)
    processor = LandmarkRuleProcessor(
        rules=(rule,),
        thresholds=THRESHOLDS,
        priority=RulesPriority.MODEL_FIRST,
    )

    with_none_model = processor.process(
        FrameContext(
            frame=_frame(),
            hands=(_hand(points=points),),
            detections=(_detection(GESTURE_NONE),),
        )
    )
    without_model = processor.process(FrameContext(frame=_frame(), hands=(_hand(points=points),)))
    no_rule_no_model = processor.process(FrameContext(frame=_frame(), hands=(_hand(),)))

    assert with_none_model.detections[0].name == GESTURE_VICTORY
    assert with_none_model.detections[0].confidence == RULE_CONFIDENCE
    assert without_model.detections[0].name == GESTURE_VICTORY
    assert no_rule_no_model.detections[0].name is GESTURE_NONE


def test_evaluate_rule_rejects_degenerate_hand() -> None:
    rule = _rule(config=GestureRuleConfig(folded=(Finger.INDEX,)))
    collapsed = _base_points()

    assert not evaluate_rule(points=collapsed, rule=rule, thresholds=THRESHOLDS)


def test_landmark_helpers_reject_wrong_point_count() -> None:
    short_points = _base_points()[:5]

    with pytest.raises(ValueError, match="landmarks"):
        is_finger_extended(
            points=short_points,
            finger=Finger.INDEX,
            straight_angle_deg=STRAIGHT_ANGLE_DEG,
        )
    with pytest.raises(ValueError, match="landmarks"):
        finger_direction(points=short_points, finger=Finger.INDEX)
    with pytest.raises(ValueError, match="landmarks"):
        matches_direction(
            points=short_points,
            condition=DirectionConditionConfig(finger=Finger.INDEX, value=Direction8.UP),
            tolerance_deg=DIRECTION_TOLERANCE_DEG,
        )
    with pytest.raises(ValueError, match="landmarks"):
        matches_angle(
            points=short_points,
            condition=AngleConditionConfig(
                a=Finger.INDEX,
                b=Finger.MIDDLE,
                min_deg=80.0,
                max_deg=100.0,
            ),
        )
