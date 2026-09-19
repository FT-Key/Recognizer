"""Tests del overlay de postura sobre fotogramas sinteticos (sin hardware)."""

import numpy as np
from numpy.typing import NDArray

from recognizer.adapters.overlay_posture import (
    BANNER_COLOR_BGR,
    HUD_BAD_COLOR_BGR,
    HUD_COLOR_BGR,
    SKELETON_BAD_COLOR_BGR,
    SKELETON_COLOR_BGR,
    SKELETON_EDGES,
    draw_posture_overlay,
)
from recognizer.core.domain.pose import COCO_KEYPOINT_ORDER, Keypoint, Pose, PoseKeypoint
from recognizer.core.domain.posture import PostureIssue

FRAME_HEIGHT = 480
FRAME_WIDTH = 640
MIN_KEYPOINT_CONFIDENCE = 0.5


def _image() -> NDArray[np.uint8]:
    return np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)


def _full_pose(*, keypoint_confidence: float = 0.9) -> Pose:
    keypoints = tuple(
        Keypoint(
            name=name,
            x=0.2 + 0.03 * index,
            y=0.2 + 0.02 * index,
            confidence=keypoint_confidence,
        )
        for index, name in enumerate(COCO_KEYPOINT_ORDER)
    )
    return Pose(confidence=0.9, keypoints=keypoints)


def _color_mask(image: NDArray[np.uint8], color: tuple[int, int, int]) -> NDArray[np.bool_]:
    return np.all(image == np.array(color, dtype=np.uint8), axis=-1)


def _draw(
    image: NDArray[np.uint8],
    *,
    poses: tuple[Pose, ...] = (),
    active: bool = False,
    issues: tuple[PostureIssue, ...] = (),
) -> None:
    draw_posture_overlay(
        image,
        poses=poses,
        active=active,
        issues=issues,
        min_keypoint_confidence=MIN_KEYPOINT_CONFIDENCE,
    )


def test_skeleton_edges_reference_coco_keypoints() -> None:
    assert SKELETON_EDGES
    for start, end in SKELETON_EDGES:
        assert start in COCO_KEYPOINT_ORDER
        assert end in COCO_KEYPOINT_ORDER


def test_draw_overlay_without_pose_draws_ok_hud() -> None:
    image = _image()

    _draw(image)

    assert _color_mask(image, HUD_COLOR_BGR).any()
    assert not _color_mask(image, HUD_BAD_COLOR_BGR).any()


def test_draw_overlay_active_draws_bad_hud_and_banner() -> None:
    image = _image()

    _draw(image, active=True, issues=(PostureIssue.HEAD_FORWARD,))

    assert _color_mask(image, HUD_BAD_COLOR_BGR).any()
    assert _color_mask(image, BANNER_COLOR_BGR).any()
    assert not _color_mask(image, HUD_COLOR_BGR).any()


def test_draw_overlay_draws_skeleton_for_confident_pose() -> None:
    with_pose = _image()
    without_pose = _image()

    _draw(with_pose, poses=(_full_pose(),))
    _draw(without_pose)

    assert (
        _color_mask(with_pose, SKELETON_COLOR_BGR).sum()
        > _color_mask(without_pose, SKELETON_COLOR_BGR).sum()
    )


def test_draw_overlay_uses_bad_skeleton_color_when_active() -> None:
    image = _image()

    _draw(image, poses=(_full_pose(),), active=True, issues=(PostureIssue.TORSO_LEAN,))

    assert _color_mask(image, SKELETON_BAD_COLOR_BGR).any()


def test_draw_overlay_skips_keypoints_below_min_confidence() -> None:
    with_low_confidence = _image()
    without_pose = _image()

    _draw(with_low_confidence, poses=(_full_pose(keypoint_confidence=0.1),))
    _draw(without_pose)

    assert np.array_equal(with_low_confidence, without_pose)


def test_draw_overlay_handles_pose_without_keypoints() -> None:
    image = _image()

    _draw(image, poses=(Pose(confidence=0.9),))

    assert _color_mask(image, HUD_COLOR_BGR).any()


def test_draw_overlay_handles_edges_with_missing_keypoint() -> None:
    partial = Pose(
        confidence=0.9,
        keypoints=(
            Keypoint(name=PoseKeypoint.NOSE, x=0.5, y=0.2, confidence=0.9),
            Keypoint(name=PoseKeypoint.LEFT_EYE, x=0.48, y=0.18, confidence=0.9),
        ),
    )
    image = _image()

    _draw(image, poses=(partial,))

    assert _color_mask(image, SKELETON_COLOR_BGR).any()
