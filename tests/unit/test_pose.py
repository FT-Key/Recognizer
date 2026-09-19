"""Tests del dominio de pose y postura ergonomica (etapa 12), sin hardware.

Cubre las validaciones de ``Keypoint``/``Pose``, la evaluacion pura
``assess_posture`` (cada habito por separado) y el debounce de ``PostureMonitor``.
"""

import pytest

from recognizer.core.domain.pose import COCO_KEYPOINT_ORDER, Keypoint, Pose, PoseKeypoint
from recognizer.core.domain.posture import (
    PostureAssessment,
    PostureIssue,
    PostureMonitor,
    PostureSnapshot,
    PostureThresholds,
    assess_posture,
)
from recognizer.core.errors import ConfigError

MIN_KEYPOINT_CONFIDENCE = 0.5
THRESHOLDS = PostureThresholds()


# --- Utilidades de construccion de poses ---


def _keypoint(
    name: PoseKeypoint,
    x: float,
    y: float,
    confidence: float = 0.9,
) -> Keypoint:
    return Keypoint(name=name, x=x, y=y, confidence=confidence)


def _default_points() -> dict[PoseKeypoint, tuple[float, float]]:
    """Pose erguida y centrada: sin ningun habito incorrecto."""
    return {
        PoseKeypoint.NOSE: (0.5, 0.25),
        PoseKeypoint.LEFT_SHOULDER: (0.3, 0.5),
        PoseKeypoint.RIGHT_SHOULDER: (0.7, 0.5),
        PoseKeypoint.LEFT_HIP: (0.35, 0.85),
        PoseKeypoint.RIGHT_HIP: (0.65, 0.85),
    }


def _pose(
    points: dict[PoseKeypoint, tuple[float, float]] | None = None,
    *,
    confidence: float = 0.9,
    keypoint_confidence: float = 0.9,
) -> Pose:
    resolved = _default_points() if points is None else points
    return Pose(
        confidence=confidence,
        keypoints=tuple(
            _keypoint(name, x, y, keypoint_confidence) for name, (x, y) in resolved.items()
        ),
    )


def _good_pose(*, confidence: float = 0.9) -> Pose:
    return _pose(confidence=confidence)


def _bad_pose(issue: PostureIssue, *, confidence: float = 0.9) -> Pose:
    """Pose que dispara exactamente el habito pedido."""
    points = _default_points()
    match issue:
        case PostureIssue.HEAD_FORWARD:
            points[PoseKeypoint.NOSE] = (0.7, 0.25)
        case PostureIssue.HEAD_DROP:
            points[PoseKeypoint.NOSE] = (0.5, 0.45)
        case PostureIssue.TORSO_LEAN:
            points[PoseKeypoint.LEFT_HIP] = (0.5, 0.85)
            points[PoseKeypoint.RIGHT_HIP] = (0.8, 0.85)
        case PostureIssue.SHOULDER_TILT:
            points[PoseKeypoint.RIGHT_SHOULDER] = (0.7, 0.6)
    return _pose(points, confidence=confidence)


def _assess(pose: Pose) -> PostureAssessment:
    return assess_posture(
        pose,
        thresholds=THRESHOLDS,
        min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE,
    )


def _monitor(*, confirm_frames: int = 2, release_frames: int = 2) -> PostureMonitor:
    return PostureMonitor(
        thresholds=THRESHOLDS,
        min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE,
        confirm_frames=confirm_frames,
        release_frames=release_frames,
    )


# --- Keypoint / Pose ---


def test_coco_keypoint_order_has_17_unique_points() -> None:
    assert len(COCO_KEYPOINT_ORDER) == 17
    assert len(set(COCO_KEYPOINT_ORDER)) == 17
    assert COCO_KEYPOINT_ORDER[0] is PoseKeypoint.NOSE
    assert COCO_KEYPOINT_ORDER[-1] is PoseKeypoint.RIGHT_ANKLE


def test_keypoint_stores_values() -> None:
    keypoint = _keypoint(PoseKeypoint.NOSE, 0.4, 0.6, 0.8)

    assert keypoint.name is PoseKeypoint.NOSE
    assert (keypoint.x, keypoint.y, keypoint.confidence) == (0.4, 0.6, 0.8)


@pytest.mark.parametrize("axis", ["x", "y"])
@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_keypoint_rejects_out_of_range_coordinates(axis: str, value: float) -> None:
    coords = {"x": 0.4, "y": 0.6}
    coords[axis] = value

    with pytest.raises(ConfigError, match=r"0 <= (x|y) <= 1"):
        Keypoint(name=PoseKeypoint.NOSE, x=coords["x"], y=coords["y"], confidence=0.8)


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_keypoint_rejects_out_of_range_confidence(confidence: float) -> None:
    with pytest.raises(ConfigError, match="confianza"):
        Keypoint(name=PoseKeypoint.NOSE, x=0.4, y=0.6, confidence=confidence)


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_pose_rejects_out_of_range_confidence(confidence: float) -> None:
    with pytest.raises(ConfigError, match="confianza"):
        Pose(confidence=confidence)


def test_pose_keypoint_returns_match_or_none() -> None:
    pose = _good_pose()

    assert pose.keypoint(PoseKeypoint.NOSE) is not None
    assert pose.keypoint(PoseKeypoint.LEFT_ANKLE) is None


def test_pose_defaults_to_no_keypoints() -> None:
    pose = Pose(confidence=0.5)

    assert pose.keypoints == ()
    assert pose.keypoint(PoseKeypoint.NOSE) is None


# --- assess_posture ---


def test_assess_good_posture_has_no_issues_and_is_evaluated() -> None:
    assessment = _assess(_good_pose())

    assert assessment.evaluated is True
    assert assessment.issues == ()
    assert assessment.is_bad is False


@pytest.mark.parametrize(
    "issue",
    [
        PostureIssue.HEAD_FORWARD,
        PostureIssue.HEAD_DROP,
        PostureIssue.TORSO_LEAN,
        PostureIssue.SHOULDER_TILT,
    ],
)
def test_assess_detects_each_issue_in_isolation(issue: PostureIssue) -> None:
    assessment = _assess(_bad_pose(issue))

    assert assessment.evaluated is True
    assert assessment.issues == (issue,)
    assert assessment.is_bad is True


def test_assess_without_required_keypoint_is_not_evaluated() -> None:
    points = _default_points()
    points.pop(PoseKeypoint.NOSE)

    assessment = _assess(_pose(points))

    assert assessment.evaluated is False
    assert assessment.issues == ()
    assert assessment.is_bad is False


def test_assess_with_low_keypoint_confidence_is_not_evaluated() -> None:
    assessment = _assess(_pose(keypoint_confidence=0.4))

    assert assessment.evaluated is False


def test_assess_with_zero_shoulder_width_is_not_evaluated() -> None:
    points = _default_points()
    points[PoseKeypoint.LEFT_SHOULDER] = (0.5, 0.5)
    points[PoseKeypoint.RIGHT_SHOULDER] = (0.5, 0.5)

    assessment = _assess(_pose(points))

    assert assessment.evaluated is False


def test_assessment_is_bad_follows_issues() -> None:
    assert PostureAssessment(evaluated=True, issues=()).is_bad is False
    assert PostureAssessment(evaluated=True, issues=(PostureIssue.HEAD_DROP,)).is_bad is True
    assert PostureAssessment(evaluated=False).is_bad is False


# --- PostureMonitor ---


def test_monitor_confirms_bad_posture_after_confirm_frames() -> None:
    monitor = _monitor(confirm_frames=2, release_frames=2)
    bad = _bad_pose(PostureIssue.HEAD_FORWARD)

    first = monitor.update((bad,))
    second = monitor.update((bad,))

    assert first == PostureSnapshot(active=False, issues=())
    assert second.active is True
    assert second.issues == (PostureIssue.HEAD_FORWARD,)


def test_monitor_releases_bad_posture_after_release_frames() -> None:
    monitor = _monitor(confirm_frames=1, release_frames=2)
    bad = _bad_pose(PostureIssue.HEAD_DROP)
    good = _good_pose()

    assert monitor.update((bad,)).active is True
    assert monitor.update((good,)).active is True
    released = monitor.update((good,))

    assert released.active is False
    assert released.issues == ()


def test_monitor_releases_when_no_pose_is_evaluable() -> None:
    monitor = _monitor(confirm_frames=1, release_frames=1)
    bad = _bad_pose(PostureIssue.TORSO_LEAN)

    assert monitor.update((bad,)).active is True
    released = monitor.update(())

    assert released.active is False
    assert released.issues == ()


def test_monitor_counts_non_evaluable_pose_as_good() -> None:
    monitor = _monitor(confirm_frames=1, release_frames=1)
    bad = _bad_pose(PostureIssue.SHOULDER_TILT)
    points = _default_points()
    points.pop(PoseKeypoint.NOSE)

    assert monitor.update((bad,)).active is True
    assert monitor.update((_pose(points),)).active is False


def test_monitor_uses_highest_confidence_evaluable_pose() -> None:
    monitor = _monitor(confirm_frames=1, release_frames=1)
    bad_high = _bad_pose(PostureIssue.HEAD_FORWARD, confidence=0.9)
    good_low = _good_pose(confidence=0.5)

    assert monitor.update((good_low, bad_high)).active is True


def test_monitor_ignores_low_confidence_bad_pose_when_good_pose_is_fiable() -> None:
    monitor = _monitor(confirm_frames=1, release_frames=1)
    good_high = _good_pose(confidence=0.9)
    bad_low = _bad_pose(PostureIssue.HEAD_FORWARD, confidence=0.5)

    assert monitor.update((bad_low, good_high)).active is False


def test_monitor_requires_reconfirm_after_release() -> None:
    monitor = _monitor(confirm_frames=1, release_frames=1)
    bad = _bad_pose(PostureIssue.HEAD_FORWARD)
    good = _good_pose()

    assert monitor.update((bad,)).active is True
    assert monitor.update((good,)).active is False
    assert monitor.update((bad,)).active is True


def test_monitor_reset_clears_state() -> None:
    monitor = _monitor(confirm_frames=1, release_frames=1)
    assert monitor.update((_bad_pose(PostureIssue.HEAD_DROP),)).active is True

    monitor.reset()

    assert monitor.update(()).active is False


@pytest.mark.parametrize("value", [0, -1])
def test_monitor_rejects_bad_confirm_frames(value: int) -> None:
    with pytest.raises(ConfigError, match="confirm_frames >= 1"):
        PostureMonitor(
            thresholds=THRESHOLDS,
            min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE,
            confirm_frames=value,
            release_frames=1,
        )


@pytest.mark.parametrize("value", [0, -1])
def test_monitor_rejects_bad_release_frames(value: int) -> None:
    with pytest.raises(ConfigError, match="release_frames >= 1"):
        PostureMonitor(
            thresholds=THRESHOLDS,
            min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE,
            confirm_frames=1,
            release_frames=value,
        )
