"""Tests del catalogo de aplicaciones del launcher."""

from pathlib import Path
from typing import cast

import pytest

from recognizer.core.domain.app import (
    DEFAULT_APPS,
    AppAvailability,
    AppCatalog,
    AppId,
    AppInfo,
    AppPreparation,
    AppRunRequest,
)
from recognizer.core.errors import ConfigError


def test_catalog_order_is_gestures_then_no_training_then_training() -> None:
    ids = [info.app_id for info in DEFAULT_APPS]

    assert ids == [
        AppId.GESTURES,
        AppId.PEOPLE_COUNTER,
        AppId.ANTI_INTRUDER,
        AppId.POSTURE,
        AppId.FACE_AUTH,
        AppId.ASSISTANCE,
        AppId.LOITERING,
        AppId.VACANCY,
        AppId.VEHICLE_COUNTER,
        AppId.PRIVACY_BLUR,
        AppId.FALL_DETECTOR,
        AppId.GENDER_AGE,
        AppId.DROWSINESS,
        AppId.OCR_READER,
        AppId.PPE_DETECTOR,
        AppId.INVENTORY,
    ]


def test_implemented_apps_are_in_order() -> None:
    implemented = [info.app_id for info in DEFAULT_APPS if info.implemented]

    assert implemented == [
        AppId.GESTURES,
        AppId.PEOPLE_COUNTER,
        AppId.ANTI_INTRUDER,
        AppId.POSTURE,
        AppId.FACE_AUTH,
        AppId.ASSISTANCE,
        AppId.LOITERING,
        AppId.VACANCY,
        AppId.VEHICLE_COUNTER,
        AppId.PRIVACY_BLUR,
    ]


def test_no_training_apps_have_no_preparation() -> None:
    no_training = {
        AppId.PEOPLE_COUNTER,
        AppId.ANTI_INTRUDER,
        AppId.POSTURE,
        AppId.ASSISTANCE,
        AppId.LOITERING,
        AppId.VACANCY,
        AppId.VEHICLE_COUNTER,
        AppId.PRIVACY_BLUR,
        AppId.FALL_DETECTOR,
        AppId.GENDER_AGE,
        AppId.DROWSINESS,
        AppId.OCR_READER,
    }

    for info in DEFAULT_APPS:
        if info.app_id in no_training:
            assert info.preparation is None


def test_training_and_enrollment_apps_declare_preparation() -> None:
    catalog = AppCatalog()

    assert catalog.require(AppId.PPE_DETECTOR).preparation is AppPreparation.TRAINING
    assert catalog.require(AppId.INVENTORY).preparation is AppPreparation.TRAINING
    assert catalog.require(AppId.FACE_AUTH).preparation is AppPreparation.ENROLLMENT


def test_by_id_returns_none_for_unknown() -> None:
    catalog = AppCatalog()

    assert catalog.by_id(AppId.GESTURES) is not None
    assert catalog.by_id(cast(AppId, "desconocida")) is None


def test_require_raises_for_unknown() -> None:
    catalog = AppCatalog()

    with pytest.raises(ConfigError, match="Aplicacion desconocida"):
        catalog.require(cast(AppId, "desconocida"))


def test_by_number_is_one_based() -> None:
    catalog = AppCatalog()

    assert catalog.by_number(1) is catalog.apps[0]
    assert catalog.by_number(0) is None
    assert catalog.by_number(len(catalog.apps) + 1) is None


def test_availability_available_when_implemented_and_enabled() -> None:
    catalog = AppCatalog()

    assert catalog.availability(AppId.GESTURES, enabled={}) is AppAvailability.AVAILABLE


def test_availability_disabled_when_config_disables_it() -> None:
    catalog = AppCatalog()

    assert (
        catalog.availability(AppId.GESTURES, enabled={AppId.GESTURES: False})
        is AppAvailability.DISABLED
    )


def test_availability_coming_soon_for_unimplemented_apps() -> None:
    catalog = AppCatalog()

    assert (
        catalog.availability(AppId.PPE_DETECTOR, enabled={AppId.PPE_DETECTOR: True})
        is AppAvailability.COMING_SOON
    )


def test_app_info_defaults() -> None:
    info = AppInfo(app_id=AppId.GESTURES, title="t", description="d")

    assert info.implemented is False
    assert info.preparation is None


def test_run_request_defaults() -> None:
    request = AppRunRequest(config_path=Path("config.yaml"))

    assert request.device is None
    assert request.max_frames == 0
    assert request.show_window is True
