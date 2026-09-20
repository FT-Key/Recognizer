"""Tests del dominio facial: vectores, captura, enrolamiento, matching y debounce.

Sin hardware: embeddings y cajas sinteticas, sin camara ni modelos reales.
"""

import math

import pytest

from recognizer.core.constants import FACE_MAX_COSINE_DISTANCE
from recognizer.core.domain.access import AccessEvent
from recognizer.core.domain.face import (
    ENROLLMENT_STEPS,
    CaptureGuidance,
    EnrolledFace,
    EnrollmentBuilder,
    FaceBox,
    FaceEmbedding,
    FaceMatch,
    FaceMatcher,
    FaceObservation,
    LoginDebouncer,
    assess_capture,
    cosine_distance,
    face_width_ratio,
    l2_normalize,
    mean_embedding,
    new_face_id,
    normalize_national_id,
    validate_national_id,
)
from recognizer.core.domain.identity import Role
from recognizer.core.errors import ConfigError

UNIT_X: FaceEmbedding = (1.0, 0.0)
UNIT_Y: FaceEmbedding = (0.0, 1.0)
GOOD_SHARPNESS = 100.0
BLURRY_SHARPNESS = 5.0


def _centered_box(width: float = 0.3) -> FaceBox:
    half = width / 2.0
    return FaceBox(
        x_min=0.5 - half,
        y_min=0.5 - half,
        x_max=0.5 + half,
        y_max=0.5 + half,
        confidence=0.9,
    )


def _observation(
    embedding: FaceEmbedding = UNIT_X,
    box: FaceBox | None = None,
    sharpness: float = GOOD_SHARPNESS,
) -> FaceObservation:
    return FaceObservation(
        embedding=embedding, box=box if box is not None else _centered_box(), sharpness=sharpness
    )


def _enrolled(face_id: str = "F-0001", name: str = "Ada") -> EnrolledFace:
    return EnrolledFace(
        face_id=face_id,
        name=name,
        embedding=UNIT_X,
        samples=2,
        created_at="2026-09-19T00:00:00+00:00",
    )


def test_l2_normalize_unit_vector_keeps_direction() -> None:
    assert l2_normalize((3.0, 4.0)) == pytest.approx((0.6, 0.8))


def test_l2_normalize_zero_vector_stays_zero() -> None:
    assert l2_normalize((0.0, 0.0)) == (0.0, 0.0)


def test_mean_embedding_single_vector_normalizes() -> None:
    result = mean_embedding(((3.0, 4.0),))
    assert result == pytest.approx((0.6, 0.8))


def test_mean_embedding_averages_and_normalizes() -> None:
    result = mean_embedding((UNIT_X, UNIT_Y))
    expected = math.sqrt(2.0) / 2.0
    assert result == pytest.approx((expected, expected))


def test_mean_embedding_empty_raises() -> None:
    with pytest.raises(ValueError, match="al menos un embedding"):
        mean_embedding(())


def test_mean_embedding_mismatched_dimensions_raise() -> None:
    with pytest.raises(ValueError, match="misma dimension"):
        mean_embedding(((1.0, 0.0), (1.0, 0.0, 0.0)))


def test_cosine_distance_identical_is_zero() -> None:
    assert cosine_distance(UNIT_X, UNIT_X) == pytest.approx(0.0)


def test_cosine_distance_orthogonal_is_one() -> None:
    assert cosine_distance(UNIT_X, UNIT_Y) == pytest.approx(1.0)


def test_cosine_distance_opposite_is_max() -> None:
    opposite: FaceEmbedding = (-1.0, 0.0)
    assert cosine_distance(UNIT_X, opposite) == pytest.approx(FACE_MAX_COSINE_DISTANCE)


def test_cosine_distance_null_vector_is_max() -> None:
    assert cosine_distance((0.0, 0.0), UNIT_X) == FACE_MAX_COSINE_DISTANCE


def test_cosine_distance_mismatched_dimensions_raise() -> None:
    with pytest.raises(ValueError, match="misma dimension"):
        cosine_distance((1.0, 0.0), (1.0,))


def test_face_width_ratio_returns_box_width() -> None:
    assert face_width_ratio(_centered_box(width=0.3)) == pytest.approx(0.3)


def test_assess_capture_close_when_too_far() -> None:
    assert assess_capture(_centered_box(width=0.1), GOOD_SHARPNESS) is CaptureGuidance.MOVE_CLOSER


def test_assess_capture_far_when_too_close() -> None:
    assert assess_capture(_centered_box(width=0.8), GOOD_SHARPNESS) is CaptureGuidance.MOVE_FARTHER


def test_assess_capture_hold_still_when_blurry() -> None:
    assert assess_capture(_centered_box(), BLURRY_SHARPNESS) is CaptureGuidance.HOLD_STILL


def test_assess_capture_center_when_off_center() -> None:
    box = FaceBox(x_min=0.05, y_min=0.35, x_max=0.35, y_max=0.65, confidence=0.9)
    assert assess_capture(box, GOOD_SHARPNESS) is CaptureGuidance.CENTER_FACE


def test_assess_capture_good_when_centered_and_sharp() -> None:
    assert assess_capture(_centered_box(), GOOD_SHARPNESS) is CaptureGuidance.GOOD


def test_new_face_id_has_expected_shape() -> None:
    face_id = new_face_id([], choice=lambda alphabet: alphabet[0])

    assert face_id == "F-AAAA"
    assert face_id.startswith("F-")
    assert len(face_id) == 6


def test_new_face_id_avoids_collisions() -> None:
    letters = iter(["A", "A", "A", "A", "B", "B", "B", "B"])
    face_id = new_face_id(["F-AAAA"], choice=lambda _alphabet: next(letters))

    assert face_id == "F-BBBB"


def test_new_face_id_accepts_mapping() -> None:
    face_id = new_face_id({"F-AAAA": object()}, choice=lambda alphabet: alphabet[1])

    assert face_id == "F-BBBB"


def test_new_face_id_exhausted_raises() -> None:
    with pytest.raises(ValueError, match="libre"):
        new_face_id(["F-AAAA"], choice=lambda _alphabet: "A")


def test_enrollment_builder_rejects_bad_samples_required() -> None:
    with pytest.raises(ConfigError, match="samples_required"):
        EnrollmentBuilder(samples_required=0)


def test_enrollment_builder_rejects_bad_width_range() -> None:
    with pytest.raises(ConfigError, match="min_width"):
        EnrollmentBuilder(min_width=0.6, max_width=0.4)


def test_enrollment_builder_rejects_negative_sharpness() -> None:
    with pytest.raises(ConfigError, match="min_sharpness"):
        EnrollmentBuilder(min_sharpness=-1.0)


def test_enrollment_builder_accepts_good_sample() -> None:
    builder = EnrollmentBuilder(samples_required=2)
    assert builder.add(_observation()) is None
    assert builder.accepted == 1
    assert not builder.is_complete


def test_enrollment_builder_rejects_far_sample_with_guidance() -> None:
    builder = EnrollmentBuilder(samples_required=2)
    guidance = builder.add(_observation(box=_centered_box(width=0.05)))
    assert guidance is CaptureGuidance.MOVE_CLOSER
    assert builder.accepted == 0


def test_enrollment_builder_completes_and_builds() -> None:
    builder = EnrollmentBuilder(samples_required=2)
    assert builder.add(_observation(embedding=UNIT_X)) is None
    assert builder.add(_observation(embedding=UNIT_Y)) is None
    assert builder.is_complete
    face = builder.build("F-0001", "  Ada  ")
    assert face.face_id == "F-0001"
    assert face.name == "Ada"
    assert face.samples == 2
    assert face.embedding == pytest.approx((math.sqrt(2.0) / 2.0, math.sqrt(2.0) / 2.0))


def test_enrollment_builder_build_incomplete_raises() -> None:
    builder = EnrollmentBuilder(samples_required=2)
    builder.add(_observation())
    with pytest.raises(ValueError, match="Faltan muestras"):
        builder.build("F-0001", "Ada")


def test_enrollment_builder_build_blank_name_raises() -> None:
    builder = EnrollmentBuilder(samples_required=1)
    builder.add(_observation())
    with pytest.raises(ValueError, match="nombre no vacio"):
        builder.build("F-0001", "   ")


def test_enrolled_face_default_password_hash_is_empty() -> None:
    assert _enrolled().password_hash == ""


def test_enrollment_builder_build_keeps_password_hash() -> None:
    builder = EnrollmentBuilder(samples_required=1)
    builder.add(_observation())
    encoded = "pbkdf2_sha256$1000$c2FsdA==$aGFzaA=="

    face = builder.build("F-0001", "Ada", password_hash=encoded)

    assert face.password_hash == encoded


def test_enrolled_face_default_national_id_is_empty() -> None:
    assert _enrolled().national_id == ""


def test_enrollment_builder_build_keeps_national_id() -> None:
    builder = EnrollmentBuilder(samples_required=1)
    builder.add(_observation())

    face = builder.build("F-0001", "Ada", national_id="12345678")

    assert face.national_id == "12345678"


def test_normalize_national_id_strips_dots_and_spaces() -> None:
    assert normalize_national_id("12.345.678") == "12345678"
    assert normalize_national_id("  1234567  ") == "1234567"


def test_validate_national_id_accepts_seven_or_eight_digits() -> None:
    assert validate_national_id("12.345.678") == "12345678"
    assert validate_national_id("1234567") == "1234567"


def test_validate_national_id_rejects_invalid() -> None:
    with pytest.raises(ValueError, match="vacio"):
        validate_national_id("   ")
    with pytest.raises(ValueError, match="digitos"):
        validate_national_id("123456")
    with pytest.raises(ValueError, match="digitos"):
        validate_national_id("123456789")
    with pytest.raises(ValueError, match="digitos"):
        validate_national_id("12A45678")


def test_enrollment_builder_current_step_cycles_prompts() -> None:
    builder = EnrollmentBuilder(samples_required=2)
    first = builder.current_step()
    builder.add(_observation())
    second = builder.current_step()
    assert first.prompt.strip()
    assert second.prompt.strip()
    assert first.step != second.step


def test_enrollment_steps_has_five_non_empty_prompts() -> None:
    assert len(ENROLLMENT_STEPS) == 5
    assert len({spec.step for spec in ENROLLMENT_STEPS}) == 5
    for spec in ENROLLMENT_STEPS:
        assert spec.prompt.strip()


def test_face_matcher_rejects_negative_threshold() -> None:
    with pytest.raises(ConfigError, match="threshold"):
        FaceMatcher(threshold=-0.1)


def test_face_matcher_empty_gallery_not_accepted() -> None:
    match = FaceMatcher().identify(UNIT_X, ())
    assert match == FaceMatch(face=None, distance=FACE_MAX_COSINE_DISTANCE, accepted=False)


def test_face_matcher_accepts_close_embedding() -> None:
    matcher = FaceMatcher(threshold=0.45)
    match = matcher.identify(UNIT_X, (_enrolled(),))
    assert match.accepted
    assert match.face is not None
    assert match.face.face_id == "F-0001"


def test_face_matcher_rejects_far_embedding() -> None:
    matcher = FaceMatcher(threshold=0.45)
    opposite: FaceEmbedding = (-1.0, 0.0)
    match = matcher.identify(opposite, (_enrolled(),))
    assert not match.accepted


def test_face_matcher_picks_closest() -> None:
    matcher = FaceMatcher(threshold=0.45)
    far = EnrolledFace(
        face_id="F-0002",
        name="Bo",
        embedding=(0.0, 1.0),
        samples=2,
        created_at="2026-09-19T00:00:00+00:00",
    )
    match = matcher.identify(UNIT_X, (far, _enrolled()))
    assert match.face is not None
    assert match.face.face_id == "F-0001"


def test_login_debouncer_rejects_bad_frames() -> None:
    with pytest.raises(ConfigError, match="confirm_frames"):
        LoginDebouncer(confirm_frames=0)
    with pytest.raises(ConfigError, match="release_frames"):
        LoginDebouncer(release_frames=0)


def test_login_debouncer_confirms_after_streak() -> None:
    debouncer = LoginDebouncer(confirm_frames=2, release_frames=2)
    face = _enrolled()
    accepted = FaceMatch(face=face, distance=0.0, accepted=True)
    assert debouncer.update(accepted) is None
    assert debouncer.update(accepted) is face


def test_login_debouncer_switching_identity_restarts_streak() -> None:
    debouncer = LoginDebouncer(confirm_frames=2, release_frames=5)
    face_a = _enrolled("F-0001", "Ada")
    face_b = _enrolled("F-0002", "Bo")
    debouncer.update(FaceMatch(face=face_a, distance=0.0, accepted=True))
    assert debouncer.update(FaceMatch(face=face_b, distance=0.0, accepted=True)) is None
    assert debouncer.update(FaceMatch(face=face_b, distance=0.0, accepted=True)) is face_b


def test_login_debouncer_releases_after_absence() -> None:
    debouncer = LoginDebouncer(confirm_frames=1, release_frames=2)
    face = _enrolled()
    debouncer.update(FaceMatch(face=face, distance=0.0, accepted=True))
    missed = FaceMatch(face=None, distance=FACE_MAX_COSINE_DISTANCE, accepted=False)
    assert debouncer.update(missed) is face
    assert debouncer.update(missed) is None


def test_login_debouncer_reset_clears_identity() -> None:
    debouncer = LoginDebouncer(confirm_frames=1, release_frames=5)
    face = _enrolled()
    debouncer.update(FaceMatch(face=face, distance=0.0, accepted=True))
    debouncer.reset()
    missed = FaceMatch(face=None, distance=FACE_MAX_COSINE_DISTANCE, accepted=False)
    assert debouncer.update(missed) is None


def test_access_event_defaults_image_to_empty() -> None:
    event = AccessEvent(
        face_id="F-0001",
        name="Ada",
        role=Role.OPERATOR,
        timestamp="2026-09-19T12:00:00+00:00",
    )

    assert event.image == ""


def test_access_event_keeps_explicit_image() -> None:
    event = AccessEvent(
        face_id="F-0001",
        name="Ada",
        role=Role.ADMIN,
        timestamp="2026-09-19T12:00:00+00:00",
        image="2026-09-19T12_00_00_00_00_F-0001.png",
    )

    assert event.image == "2026-09-19T12_00_00_00_00_F-0001.png"
    assert event.role is Role.ADMIN


def test_access_event_is_frozen() -> None:
    event = AccessEvent(
        face_id="F-0001",
        name="Ada",
        role=Role.OPERATOR,
        timestamp="2026-09-19T12:00:00+00:00",
    )

    with pytest.raises(AttributeError):
        setattr(event, "name", "Bo")  # noqa: B010 - ejerce el frozen a proposito
