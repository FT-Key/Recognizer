"""Tests del menu y la configuracion de la app facial, sin hardware.

Verifica que el launcher resuelve el runner facial con import perezoso
(sin cargar InsightFace al abrir el menu) y que ``config.yaml`` expone la
seccion ``face_auth``.
"""

import inspect
import sys
from pathlib import Path

import pytest

from recognizer.cli import menu
from recognizer.core.config import FaceAuthConfig
from recognizer.core.constants import (
    DEFAULT_FACE_DET_SIZE,
    DEFAULT_FACE_MAX_INFERENCE_FPS,
    DEFAULT_FACE_PROCESS_EVERY_N_FRAMES,
    FACE_AUTH_MODEL_PATH,
)
from recognizer.core.domain.app import AppId
from recognizer.core.errors import ConfigError
from recognizer.settings import load_config

FACE_YAML = """
face_auth:
  model_path: models/buffalo_s
  min_confidence: 0.6
  enrollment_samples: 3
  match_threshold: 0.4
  store_dir: data/faces
"""

BAD_WIDTHS_YAML = """
face_auth:
  min_face_width_ratio: 0.6
  max_face_width_ratio: 0.4
"""


def _write_config(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_resolve_runner_face_auth_returns_face_runner() -> None:
    from recognizer.cli.apps.face_auth import run_face_auth

    assert menu.resolve_runner(AppId.FACE_AUTH) is run_face_auth


def test_menu_module_does_not_import_insightface() -> None:
    source = inspect.getsource(menu)
    assert "insightface" not in source
    assert "insightface" not in sys.modules


def test_resolve_runner_face_auth_is_lazy_import() -> None:
    source = inspect.getsource(menu.resolve_runner)
    assert "run_face_auth" in source


def test_face_auth_config_defaults() -> None:
    config = FaceAuthConfig()
    assert config.model_path == FACE_AUTH_MODEL_PATH
    assert config.min_face_width_ratio < config.max_face_width_ratio
    assert config.enrollment_samples >= 1
    assert config.det_size == DEFAULT_FACE_DET_SIZE
    assert config.process_every_n_frames == DEFAULT_FACE_PROCESS_EVERY_N_FRAMES
    assert config.max_inference_fps == DEFAULT_FACE_MAX_INFERENCE_FPS


def test_face_auth_config_rejects_invalid_latency_tuning() -> None:
    with pytest.raises(ValueError, match="det_size"):
        FaceAuthConfig(det_size=64)
    with pytest.raises(ValueError, match="process_every_n_frames"):
        FaceAuthConfig(process_every_n_frames=0)
    with pytest.raises(ValueError, match="max_inference_fps"):
        FaceAuthConfig(max_inference_fps=-1)


def test_load_config_reads_face_auth_section(tmp_path: Path) -> None:
    config = load_config(_write_config(tmp_path, FACE_YAML))
    assert config.face_auth.model_path == "models/buffalo_s"
    assert config.face_auth.min_confidence == pytest.approx(0.6)
    assert config.face_auth.enrollment_samples == 3
    assert config.face_auth.match_threshold == pytest.approx(0.4)
    assert config.face_auth.store_dir == "data/faces"


def test_load_config_rejects_inverted_face_widths(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="min_face_width_ratio"):
        load_config(_write_config(tmp_path, BAD_WIDTHS_YAML))
