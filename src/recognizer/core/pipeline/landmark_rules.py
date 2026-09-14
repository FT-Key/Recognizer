"""Motor de reglas geometricas de gestos a partir de landmarks.

Modulo de core puro: no depende de OpenCV ni MediaPipe. Las condiciones de una
regla (dedos extendidos/doblados, direccion y angulo entre dedos) se evaluan
sobre los 21 puntos normalizados que ya produce el detector de manos.
"""

import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass, replace

from recognizer.core.config import (
    AngleConditionConfig,
    DirectionConditionConfig,
    DistanceConditionConfig,
    GestureRuleConfig,
    RuleThresholdsConfig,
)
from recognizer.core.constants import MIN_ANGLE_DEG, MIN_VECTOR_NORM, RULE_CONFIDENCE
from recognizer.core.domain.gesture import (
    GESTURE_NONE,
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
    WRIST_LANDMARK_INDEX,
    HandLandmarks,
    Point,
)
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.pipeline.processor import Processor

_rule_log = logging.getLogger("recognizer.rules_diag")

# Coordenadas de imagen: x crece a la derecha e y crece hacia abajo. Por eso
# "arriba" es -90 grados en la convencion de atan2(dy, dx).
FULL_CIRCLE_DEG = 360.0
ZERO_DEG = 0.0
ANGLE_SECTOR_DEG = 45.0
RIGHT_ANGLE_DEG = 90.0
STRAIGHT_TURN_DEG = 180.0
MIN_COSINE = -1.0
MAX_COSINE = 1.0
INITIAL_CONFIDENCE = 0.0

DIRECTION_CENTERS_DEG: dict[Direction8, float] = {
    Direction8.RIGHT: ZERO_DEG,
    Direction8.DOWN_RIGHT: ANGLE_SECTOR_DEG,
    Direction8.DOWN: RIGHT_ANGLE_DEG,
    Direction8.DOWN_LEFT: STRAIGHT_TURN_DEG - ANGLE_SECTOR_DEG,
    Direction8.LEFT: STRAIGHT_TURN_DEG,
    Direction8.UP_LEFT: -(STRAIGHT_TURN_DEG - ANGLE_SECTOR_DEG),
    Direction8.UP: -RIGHT_ANGLE_DEG,
    Direction8.UP_RIGHT: -ANGLE_SECTOR_DEG,
}

DIRECTION_ORDER: tuple[Direction8, ...] = (
    Direction8.UP,
    Direction8.UP_RIGHT,
    Direction8.RIGHT,
    Direction8.DOWN_RIGHT,
    Direction8.DOWN,
    Direction8.DOWN_LEFT,
    Direction8.LEFT,
    Direction8.UP_LEFT,
)

# Triple (base, vertice, punta) para medir si un dedo esta extendido. El pulgar
# no tiene PIP: se usa MCP-IP-TIP.
_ANGLE_LANDMARKS: dict[Finger, tuple[int, int, int]] = {
    Finger.THUMB: (THUMB_MCP_LANDMARK_INDEX, THUMB_IP_LANDMARK_INDEX, THUMB_TIP_LANDMARK_INDEX),
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

# Par (base, punta) para estimar la direccion del dedo en el plano.
_DIRECTION_LANDMARKS: dict[Finger, tuple[int, int]] = {
    Finger.THUMB: (THUMB_MCP_LANDMARK_INDEX, THUMB_TIP_LANDMARK_INDEX),
    Finger.INDEX: (INDEX_FINGER_MCP_LANDMARK_INDEX, INDEX_FINGER_TIP_LANDMARK_INDEX),
    Finger.MIDDLE: (MIDDLE_FINGER_MCP_LANDMARK_INDEX, MIDDLE_FINGER_TIP_LANDMARK_INDEX),
    Finger.RING: (RING_FINGER_MCP_LANDMARK_INDEX, RING_FINGER_TIP_LANDMARK_INDEX),
    Finger.PINKY: (PINKY_MCP_LANDMARK_INDEX, PINKY_TIP_LANDMARK_INDEX),
}


def _angle_deg(a: Point, b: Point, c: Point) -> float:
    """Angulo en el vertice ``b`` del triplete ``a-b-c`` usando solo x,y.

    Si alguno de los vectores es degenerado (magnitud ~0) devuelve 0.
    """
    ax = a.x - b.x
    ay = a.y - b.y
    cx = c.x - b.x
    cy = c.y - b.y
    norm_ab = math.hypot(ax, ay)
    norm_cb = math.hypot(cx, cy)
    if norm_ab < MIN_VECTOR_NORM or norm_cb < MIN_VECTOR_NORM:
        return MIN_ANGLE_DEG
    cosine = (ax * cx + ay * cy) / (norm_ab * norm_cb)
    cosine = max(MIN_COSINE, min(MAX_COSINE, cosine))
    return math.degrees(math.acos(cosine))


def _angular_distance_deg(a: float, b: float) -> float:
    """Distancia angular minima entre dos angulos, con wrap-around, en 0..180."""
    difference = abs(a - b) % FULL_CIRCLE_DEG
    return min(difference, FULL_CIRCLE_DEG - difference)


def _ensure_landmark_count(points: Sequence[Point]) -> None:
    """Valida que la mano tenga los 21 landmarks esperados.

    Raises:
        ValueError: si el numero de landmarks no es ``HAND_LANDMARK_COUNT``.
    """
    if len(points) != HAND_LANDMARK_COUNT:
        msg = f"Se esperaban {HAND_LANDMARK_COUNT} landmarks de mano, hay {len(points)}."
        raise ValueError(msg)


def _is_degenerate_hand(points: Sequence[Point]) -> bool:
    """Detecta manos con puntos colapsados (sin extension util).

    Sin este filtro, un puñado de puntos casi identicos se clasificaria como
    todos los dedos doblados y con direccion ``right`` por ``atan2(0, 0)``,
    produciendo falsos positivos con confianza total. Se compara la dispersion
    respecto a la muñeca para no rechazar manos sinteticas de un solo dedo.
    """
    wrist = points[WRIST_LANDMARK_INDEX]
    spread = max(math.hypot(point.x - wrist.x, point.y - wrist.y) for point in points)
    return spread < MIN_VECTOR_NORM


def _finger_direction_deg(*, points: Sequence[Point], finger: Finger) -> float:
    """Angulo base->punta del dedo en grados (atan2 sobre x,y)."""
    _ensure_landmark_count(points)
    base_index, tip_index = _DIRECTION_LANDMARKS[finger]
    base = points[base_index]
    tip = points[tip_index]
    return math.degrees(math.atan2(tip.y - base.y, tip.x - base.x))


def is_finger_extended(
    *,
    points: Sequence[Point],
    finger: Finger,
    straight_angle_deg: float,
) -> bool:
    """Indica si el dedo esta extendido segun su angulo articular."""
    _ensure_landmark_count(points)
    start, vertex, end = _ANGLE_LANDMARKS[finger]
    return _angle_deg(points[start], points[vertex], points[end]) >= straight_angle_deg


def finger_direction(*, points: Sequence[Point], finger: Finger) -> Direction8:
    """Clasifica la direccion base->punta al sector de 45 grados mas cercano."""
    angle = _finger_direction_deg(points=points, finger=finger)
    return min(
        DIRECTION_ORDER,
        key=lambda direction: _angular_distance_deg(angle, DIRECTION_CENTERS_DEG[direction]),
    )


def matches_direction(
    *,
    points: Sequence[Point],
    condition: DirectionConditionConfig,
    tolerance_deg: float,
) -> bool:
    """Comprueba que un dedo apunta a la direccion objetivo dentro de tolerancia."""
    actual = _finger_direction_deg(points=points, finger=condition.finger)
    target = DIRECTION_CENTERS_DEG[condition.value]
    return _angular_distance_deg(actual, target) <= tolerance_deg


def matches_angle(*, points: Sequence[Point], condition: AngleConditionConfig) -> bool:
    """Comprueba que el angulo entre las direcciones de dos dedos cae en rango."""
    first = _finger_direction_deg(points=points, finger=condition.a)
    second = _finger_direction_deg(points=points, finger=condition.b)
    angle = _angular_distance_deg(first, second)
    return condition.min_deg <= angle <= condition.max_deg


def _finger_tip_index(finger: Finger) -> int:
    """Indice del landmark de la punta de un dedo."""
    return _DIRECTION_LANDMARKS[finger][1]


def _hand_scale(points: Sequence[Point]) -> float:
    """Tamano de la mano: distancia muneca -> MCP del dedo corazon (eje x,y)."""
    wrist = points[WRIST_LANDMARK_INDEX]
    middle_mcp = points[MIDDLE_FINGER_MCP_LANDMARK_INDEX]
    return math.hypot(middle_mcp.x - wrist.x, middle_mcp.y - wrist.y)


def matches_distance(*, points: Sequence[Point], condition: DistanceConditionConfig) -> bool:
    """Comprueba que dos puntas de dedo estan mas cerca que ``max_ratio``.

    La distancia se divide por el tamano de la mano para no depender de lo lejos
    que este la mano de la camara. Una mano degenerada (escala ~0) no hace match.
    """
    _ensure_landmark_count(points)
    scale = _hand_scale(points)
    if scale < MIN_VECTOR_NORM:
        return False
    first = points[_finger_tip_index(condition.a)]
    second = points[_finger_tip_index(condition.b)]
    distance = math.hypot(first.x - second.x, first.y - second.y)
    return distance / scale <= condition.max_ratio


@dataclass(frozen=True, slots=True)
class LandmarkRule:
    """Regla declarativa asociada al gesto que produce cuando hace match."""

    gesture: GestureId
    config: GestureRuleConfig


def evaluate_rule(
    *,
    points: Sequence[Point],
    rule: LandmarkRule,
    thresholds: RuleThresholdsConfig,
) -> bool:
    """Evalua el AND de todas las condiciones presentes en la regla."""
    if len(points) != HAND_LANDMARK_COUNT or _is_degenerate_hand(points):
        return False

    config = rule.config
    if not all(
        is_finger_extended(
            points=points,
            finger=finger,
            straight_angle_deg=thresholds.straight_angle_deg,
        )
        for finger in config.extended
    ):
        return False
    if not all(
        not is_finger_extended(
            points=points,
            finger=finger,
            straight_angle_deg=thresholds.straight_angle_deg,
        )
        for finger in config.folded
    ):
        return False
    if config.direction is not None and not matches_direction(
        points=points,
        condition=config.direction,
        tolerance_deg=thresholds.direction_tolerance_deg,
    ):
        return False
    if config.distance is not None and not matches_distance(
        points=points,
        condition=config.distance,
    ):
        return False
    return config.angle is None or matches_angle(points=points, condition=config.angle)


def match_rules(
    *,
    points: Sequence[Point],
    rules: Sequence[LandmarkRule],
    thresholds: RuleThresholdsConfig,
) -> LandmarkRule | None:
    """Devuelve la primera regla que hace match, respetando su orden."""
    for rule in rules:
        if evaluate_rule(points=points, rule=rule, thresholds=thresholds):
            return rule
    return None


class LandmarkRuleProcessor(Processor):
    """Resuelve cada mano entre el modelo de gestos y las reglas de landmarks."""

    def __init__(
        self,
        *,
        rules: Sequence[LandmarkRule],
        thresholds: RuleThresholdsConfig,
        priority: RulesPriority,
    ) -> None:
        self._rules = rules
        self._thresholds = thresholds
        self._priority = priority

    def process(self, context: FrameContext) -> FrameContext:
        """Anota una deteccion por mano segun la prioridad configurada."""
        detections = tuple(
            self._detect(hand=hand, model=self._model_at(context.detections, index))
            for index, hand in enumerate(context.hands)
        )
        return replace(context, detections=detections)

    def _detect(self, *, hand: HandLandmarks, model: DetectedGesture | None) -> DetectedGesture:
        rule = match_rules(points=hand.points, rules=self._rules, thresholds=self._thresholds)
        if rule is not None:
            _rule_log.debug(
                "[RULE-DIAG] hand=%s RULE_MATCH=%s model=%s priority=%s",
                hand.handedness.value,
                rule.gesture.value,
                model.name.value if model else "None",
                self._priority.value,
            )
        if self._priority is RulesPriority.RULES_FIRST:
            if rule is not None:
                return self._from_rule(hand=hand, rule=rule)
            return model if model is not None else self._none(hand=hand)
        if model is not None and model.name != GESTURE_NONE:
            return model
        if rule is not None:
            return self._from_rule(hand=hand, rule=rule)
        return self._none(hand=hand)

    @staticmethod
    def _model_at(
        detections: Sequence[DetectedGesture],
        index: int,
    ) -> DetectedGesture | None:
        """Devuelve la deteccion del modelo para la mano ``index``, si existe."""
        return detections[index] if index < len(detections) else None

    @staticmethod
    def _from_rule(*, hand: HandLandmarks, rule: LandmarkRule) -> DetectedGesture:
        return DetectedGesture(
            name=rule.gesture,
            confidence=RULE_CONFIDENCE,
            handedness=hand.handedness,
        )

    @staticmethod
    def _none(*, hand: HandLandmarks) -> DetectedGesture:
        return DetectedGesture(
            name=GESTURE_NONE,
            confidence=INITIAL_CONFIDENCE,
            handedness=hand.handedness,
        )
