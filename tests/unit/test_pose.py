"""Tests del dominio de pose y postura ergonomica (etapa 12), sin hardware.

Cubre las validaciones de ``Keypoint``/``Pose``, la medicion parcial
``measure_posture`` (metricas por separado, escala de perfil), la evaluacion pura
``assess_posture`` y la calibracion + debounce de ``PostureMonitor``.
"""

import pytest

from recognizer.core.domain.pose import COCO_KEYPOINT_ORDER, Keypoint, Pose, PoseKeypoint
from recognizer.core.domain.posture import (
    PostureAssessment,
    PostureIssue,
    PostureMetrics,
    PostureMonitor,
    PostureSnapshot,
    PostureThresholds,
    PostureTolerances,
    assess_posture,
    measure_posture,
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
    """Pose erguida y centrada: sin ningun habito incorrecto.

    El ancho de hombros (0.4) es la escala: la nariz queda a 0.75 de altura
    normalizada sobre los hombros, por encima del minimo (0.7).
    """
    return {
        PoseKeypoint.NOSE: (0.5, 0.2),
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
    """Pose que dispara exactamente el habito pedido con umbrales absolutos."""
    points = _default_points()
    match issue:
        case PostureIssue.HEAD_FORWARD:
            points[PoseKeypoint.NOSE] = (0.7, 0.2)
        case PostureIssue.HEAD_DROP:
            points[PoseKeypoint.NOSE] = (0.5, 0.25)
        case PostureIssue.TORSO_LEAN:
            points[PoseKeypoint.LEFT_HIP] = (0.5, 0.85)
            points[PoseKeypoint.RIGHT_HIP] = (0.8, 0.85)
        case PostureIssue.SHOULDER_TILT:
            points[PoseKeypoint.RIGHT_SHOULDER] = (0.7, 0.6)
    return _pose(points, confidence=confidence)


def _nose_pose(x: float) -> Pose:
    """Pose erguida con la nariz desplazada horizontalmente."""
    points = _default_points()
    points[PoseKeypoint.NOSE] = (x, 0.2)
    return _pose(points)


def _deviated_pose(issue: PostureIssue) -> Pose:
    """Desvio claro respecto a la linea base de ``_good_pose``."""
    points = _default_points()
    match issue:
        case PostureIssue.HEAD_FORWARD:
            points[PoseKeypoint.NOSE] = (0.62, 0.2)
        case PostureIssue.HEAD_DROP:
            points[PoseKeypoint.NOSE] = (0.5, 0.32)
        case PostureIssue.TORSO_LEAN:
            points[PoseKeypoint.LEFT_HIP] = (0.5, 0.85)
            points[PoseKeypoint.RIGHT_HIP] = (0.8, 0.85)
        case PostureIssue.SHOULDER_TILT:
            points[PoseKeypoint.RIGHT_SHOULDER] = (0.7, 0.6)
    return _pose(points)


def _assess(pose: Pose) -> PostureAssessment:
    return assess_posture(
        pose,
        thresholds=THRESHOLDS,
        min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE,
    )


def _monitor(
    *,
    confirm_frames: int = 2,
    release_frames: int = 2,
    calibration_frames: int = 0,
    tolerances: PostureTolerances | None = None,
) -> PostureMonitor:
    return PostureMonitor(
        thresholds=THRESHOLDS,
        min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE,
        confirm_frames=confirm_frames,
        release_frames=release_frames,
        calibration_frames=calibration_frames,
        tolerances=tolerances,
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


# --- measure_posture ---


def test_measure_posture_without_hips_keeps_head_metrics() -> None:
    """Caso clave del bug: sentado, las caderas quedan ocultas por el escritorio."""
    points = _default_points()
    points.pop(PoseKeypoint.LEFT_HIP)
    points.pop(PoseKeypoint.RIGHT_HIP)

    metrics = measure_posture(_pose(points), min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE)

    assert metrics is not None
    assert metrics.torso_angle_deg is None
    assert metrics.head_offset_ratio == pytest.approx(0.0)
    assert metrics.head_height_ratio == pytest.approx(0.75)
    assert metrics.shoulder_tilt_ratio == pytest.approx(0.0)
    assert metrics.any_available() is True


def test_measure_posture_uses_torso_length_as_profile_scale() -> None:
    points = {
        PoseKeypoint.NOSE: (0.5, 0.3),
        PoseKeypoint.LEFT_SHOULDER: (0.45, 0.5),
        PoseKeypoint.RIGHT_SHOULDER: (0.55, 0.5),
        PoseKeypoint.LEFT_HIP: (0.5, 0.9),
        PoseKeypoint.RIGHT_HIP: (0.5, 0.9),
    }

    metrics = measure_posture(_pose(points), min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE)

    assert metrics is not None
    # Ancho de hombros (0.1) < 0.5 * torso (0.4): la escala es el largo del torso.
    assert metrics.head_height_ratio == pytest.approx(0.2 / 0.4)
    assert metrics.shoulder_tilt_ratio == pytest.approx(0.0)
    assert metrics.torso_angle_deg == pytest.approx(0.0)


def test_measure_posture_without_scale_returns_none() -> None:
    pose = _pose({PoseKeypoint.NOSE: (0.5, 0.2)})

    assert measure_posture(pose, min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE) is None


def test_measure_posture_with_coincident_shoulders_and_no_hips_returns_none() -> None:
    points = {
        PoseKeypoint.NOSE: (0.5, 0.2),
        PoseKeypoint.LEFT_SHOULDER: (0.5, 0.5),
        PoseKeypoint.RIGHT_SHOULDER: (0.5, 0.5),
    }

    assert measure_posture(_pose(points), min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE) is None


def test_measure_posture_without_head_keeps_torso_and_tilt() -> None:
    points = _default_points()
    points.pop(PoseKeypoint.NOSE)

    metrics = measure_posture(_pose(points), min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE)

    assert metrics is not None
    assert metrics.head_offset_ratio is None
    assert metrics.head_height_ratio is None
    assert metrics.torso_angle_deg == pytest.approx(0.0)
    assert metrics.shoulder_tilt_ratio == pytest.approx(0.0)


def test_measure_posture_torso_none_when_hips_not_below_shoulders() -> None:
    points = _default_points()
    points[PoseKeypoint.LEFT_HIP] = (0.35, 0.45)
    points[PoseKeypoint.RIGHT_HIP] = (0.65, 0.45)

    metrics = measure_posture(_pose(points), min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE)

    assert metrics is not None
    assert metrics.torso_angle_deg is None
    assert metrics.head_height_ratio == pytest.approx(0.75)


def test_measure_posture_works_with_single_shoulder_in_profile() -> None:
    # Vista de perfil: el hombro lejano queda oculto; con uno basta para medir.
    points = {
        PoseKeypoint.NOSE: (0.5, 0.2),
        PoseKeypoint.LEFT_SHOULDER: (0.3, 0.5),
        PoseKeypoint.LEFT_HIP: (0.35, 0.85),
        PoseKeypoint.RIGHT_HIP: (0.65, 0.85),
    }

    metrics = measure_posture(_pose(points), min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE)

    assert metrics is not None
    assert metrics.head_height_ratio is not None
    assert metrics.torso_angle_deg is not None
    assert metrics.shoulder_tilt_ratio is None


def test_measure_posture_uses_head_scale_without_hips_or_shoulder_pair() -> None:
    # Perfil sentado: un hombro y sin caderas -> la cabeza da la escala.
    points = {
        PoseKeypoint.NOSE: (0.5, 0.2),
        PoseKeypoint.LEFT_EAR: (0.45, 0.18),
        PoseKeypoint.RIGHT_EAR: (0.55, 0.18),
        PoseKeypoint.LEFT_SHOULDER: (0.4, 0.5),
    }

    metrics = measure_posture(_pose(points), min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE)

    assert metrics is not None
    assert metrics.head_height_ratio is not None
    assert metrics.torso_angle_deg is None
    assert metrics.shoulder_tilt_ratio is None


def test_measure_posture_with_low_keypoint_confidence_returns_none() -> None:
    pose = _pose(keypoint_confidence=0.4)

    assert measure_posture(pose, min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE) is None


def test_metrics_any_available() -> None:
    assert PostureMetrics().any_available() is False
    assert PostureMetrics(head_offset_ratio=0.1).any_available() is True
    assert PostureMetrics(torso_angle_deg=0.0).any_available() is True


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


def test_assess_with_hidden_hips_still_evaluates() -> None:
    points = _default_points()
    points.pop(PoseKeypoint.LEFT_HIP)
    points.pop(PoseKeypoint.RIGHT_HIP)

    assessment = _assess(_pose(points))

    assert assessment.evaluated is True
    assert assessment.issues == ()
    assert assessment.is_bad is False


def test_assess_without_nose_evaluates_torso_metrics() -> None:
    points = _default_points()
    points.pop(PoseKeypoint.NOSE)

    assessment = _assess(_pose(points))

    assert assessment.evaluated is True
    assert assessment.issues == ()


def test_assess_without_scale_is_not_evaluated() -> None:
    assessment = _assess(_pose({PoseKeypoint.NOSE: (0.5, 0.2)}))

    assert assessment.evaluated is False
    assert assessment.issues == ()
    assert assessment.is_bad is False


def test_assess_with_low_keypoint_confidence_is_not_evaluated() -> None:
    assessment = _assess(_pose(keypoint_confidence=0.4))

    assert assessment.evaluated is False


def test_assess_with_zero_shoulder_width_is_not_evaluated() -> None:
    points = _default_points()
    points.pop(PoseKeypoint.LEFT_HIP)
    points.pop(PoseKeypoint.RIGHT_HIP)
    points[PoseKeypoint.LEFT_SHOULDER] = (0.5, 0.5)
    points[PoseKeypoint.RIGHT_SHOULDER] = (0.5, 0.5)

    assessment = _assess(_pose(points))

    assert assessment.evaluated is False


def test_assessment_is_bad_follows_issues() -> None:
    assert PostureAssessment(evaluated=True, issues=()).is_bad is False
    assert PostureAssessment(evaluated=True, issues=(PostureIssue.HEAD_DROP,)).is_bad is True
    assert PostureAssessment(evaluated=False).is_bad is False


# --- PostureMonitor: debounce con umbrales absolutos ---


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


def test_monitor_non_evaluable_frame_does_not_break_bad_streak() -> None:
    monitor = _monitor(confirm_frames=3, release_frames=5)
    bad = _bad_pose(PostureIssue.HEAD_FORWARD)
    missing = _pose({PoseKeypoint.NOSE: (0.5, 0.2)})

    assert monitor.update((bad,)).active is False
    assert monitor.update((missing,)).active is False
    assert monitor.update((bad,)).active is False
    assert monitor.update((bad,)).active is True


def test_monitor_prolonged_missing_releases_after_release_frames() -> None:
    monitor = _monitor(confirm_frames=1, release_frames=2)
    bad = _bad_pose(PostureIssue.SHOULDER_TILT)
    missing = _pose({PoseKeypoint.NOSE: (0.5, 0.2)})

    assert monitor.update((bad,)).active is True
    assert monitor.update((missing,)).active is True
    assert monitor.update((missing,)).active is False


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


# --- PostureMonitor: calibracion ---


def test_monitor_without_calibration_uses_absolute_thresholds() -> None:
    monitor = _monitor(confirm_frames=1, release_frames=1)

    assert monitor.calibrating is False
    assert monitor.update((_bad_pose(PostureIssue.HEAD_FORWARD),)).issues == (
        PostureIssue.HEAD_FORWARD,
    )


def test_monitor_calibrates_for_n_evaluable_frames_then_monitors() -> None:
    monitor = _monitor(confirm_frames=1, release_frames=1, calibration_frames=2)
    good = _good_pose()

    assert monitor.calibrating is True
    first = monitor.update((good,))
    assert first == PostureSnapshot(active=False, calibrating=True)
    assert monitor.calibrating is True
    second = monitor.update((good,))
    assert second == PostureSnapshot(active=False, calibrating=True)
    assert monitor.calibrating is False

    monitored = monitor.update((good,))
    assert monitored == PostureSnapshot(active=False, calibrating=False)


def test_monitor_does_not_alert_while_calibrating() -> None:
    monitor = _monitor(confirm_frames=1, release_frames=1, calibration_frames=3)

    snapshot = monitor.update((_bad_pose(PostureIssue.HEAD_FORWARD),))

    assert snapshot == PostureSnapshot(active=False, calibrating=True)
    assert snapshot.issues == ()
    assert monitor.calibrating is True


def test_monitor_calibration_ignores_non_evaluable_frames() -> None:
    monitor = _monitor(confirm_frames=1, release_frames=1, calibration_frames=2)
    good = _good_pose()

    assert monitor.update(()).calibrating is True
    assert monitor.calibrating is True
    assert monitor.update((good,)).calibrating is True
    assert monitor.calibrating is True
    assert monitor.update((good,)).calibrating is True
    assert monitor.calibrating is False


def test_monitor_baseline_is_median_of_calibration_samples() -> None:
    monitor = _monitor(confirm_frames=1, release_frames=1, calibration_frames=3)

    for pose in (_good_pose(), _good_pose(), _nose_pose(0.62)):
        monitor.update((pose,))
    assert monitor.calibrating is False

    # La mediana de [0.0, 0.0, 0.3] es 0.0 (la media seria 0.1): un desvio de
    # 0.2 supera la tolerancia (0.15) solo si la linea base es la mediana.
    snapshot = monitor.update((_nose_pose(0.58),))

    assert snapshot.active is True
    assert snapshot.issues == (PostureIssue.HEAD_FORWARD,)


def test_monitor_calibrated_baseline_does_not_fire_on_same_posture() -> None:
    monitor = _monitor(confirm_frames=1, release_frames=1, calibration_frames=2)
    good = _good_pose()
    monitor.update((good,))
    monitor.update((good,))

    assert monitor.update((good,)).active is False


@pytest.mark.parametrize(
    "issue",
    [
        PostureIssue.HEAD_FORWARD,
        PostureIssue.HEAD_DROP,
        PostureIssue.TORSO_LEAN,
        PostureIssue.SHOULDER_TILT,
    ],
)
def test_monitor_baseline_detects_each_deviation(issue: PostureIssue) -> None:
    monitor = _monitor(confirm_frames=1, release_frames=1, calibration_frames=2)
    good = _good_pose()
    monitor.update((good,))
    monitor.update((good,))

    snapshot = monitor.update((_deviated_pose(issue),))

    assert snapshot.active is True
    assert snapshot.issues == (issue,)


def test_monitor_baseline_ignores_metrics_missing_in_calibration() -> None:
    monitor = _monitor(confirm_frames=1, release_frames=1, calibration_frames=2)
    points = _default_points()
    points.pop(PoseKeypoint.LEFT_HIP)
    points.pop(PoseKeypoint.RIGHT_HIP)
    no_hips = _pose(points)
    monitor.update((no_hips,))
    monitor.update((no_hips,))

    assert monitor.calibrating is False
    assert monitor.update((no_hips,)).active is False


def test_monitor_reset_restarts_calibration() -> None:
    monitor = _monitor(confirm_frames=1, release_frames=1, calibration_frames=1)
    good = _good_pose()
    assert monitor.update((good,)).calibrating is True
    assert monitor.calibrating is False

    monitor.reset()

    assert monitor.calibrating is True
    assert monitor.update((good,)) == PostureSnapshot(active=False, calibrating=True)
    assert monitor.calibrating is False


# --- PostureMonitor: validaciones ---


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


@pytest.mark.parametrize("value", [-1, -5])
def test_monitor_rejects_negative_calibration_frames(value: int) -> None:
    with pytest.raises(ConfigError, match="calibration_frames >= 0"):
        PostureMonitor(
            thresholds=THRESHOLDS,
            min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE,
            confirm_frames=1,
            release_frames=1,
            calibration_frames=value,
        )


def test_monitor_missing_alerting_metric_does_not_count_as_good_for_release() -> None:
    monitor = _monitor(confirm_frames=1, release_frames=2)
    assert monitor.update((_bad_pose(PostureIssue.HEAD_DROP),)).active is True

    # Fotograma sin nariz: no trae la metrica del aviso -> no cuenta como bueno.
    shoulders_only = _pose(
        {
            PoseKeypoint.LEFT_SHOULDER: (0.3, 0.5),
            PoseKeypoint.RIGHT_SHOULDER: (0.7, 0.5),
        }
    )
    assert monitor.update((shoulders_only,)).active is True
    assert monitor.update((_good_pose(),)).active is True
    assert monitor.update((_good_pose(),)).active is False
