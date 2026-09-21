"""Tests de la fachada InsightFace sin cargar el modelo real."""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from recognizer.adapters import insightface_recognizer as mod


def test_create_analysis_limits_modules_to_detection_and_recognition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeFaceAnalysis:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    fake_app = types.ModuleType("insightface.app")
    fake_app.FaceAnalysis = FakeFaceAnalysis  # type: ignore[attr-defined]
    fake_pkg = types.ModuleType("insightface")
    fake_pkg.app = fake_app  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "insightface", fake_pkg)
    monkeypatch.setitem(sys.modules, "insightface.app", fake_app)

    mod.create_analysis(model_path="models/buffalo_s")

    assert captured["name"] == "buffalo_s"
    assert captured["root"] == "models"
    assert captured["allowed_modules"] == list(mod.FACE_ANALYSIS_MODULES)
    assert "landmark_2d_106" not in mod.FACE_ANALYSIS_MODULES
    assert "genderage" not in mod.FACE_ANALYSIS_MODULES


def test_create_analysis_accepts_explicit_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeFaceAnalysis:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    fake_app = types.ModuleType("insightface.app")
    fake_app.FaceAnalysis = FakeFaceAnalysis  # type: ignore[attr-defined]
    fake_pkg = types.ModuleType("insightface")
    fake_pkg.app = fake_app  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "insightface", fake_pkg)
    monkeypatch.setitem(sys.modules, "insightface.app", fake_app)

    mod.create_analysis(model_path="models/buffalo_s", modules=("detection",))

    assert captured["allowed_modules"] == ["detection"]


def test_split_model_path_uses_parent_or_models() -> None:
    assert mod.split_model_path("models/buffalo_s") == ("models", "buffalo_s")
    assert mod.split_model_path("buffalo_s") == ("models", "buffalo_s")
