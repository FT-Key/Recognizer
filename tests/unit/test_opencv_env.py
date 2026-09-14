"""Tests del ajuste de entorno que acelera la camara MSMF de OpenCV en Windows."""

import os
import subprocess
import sys

HW_TRANSFORMS_ENV = "OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"
PRINT_ENV_CODE = f"import os, recognizer, cv2; print(os.environ['{HW_TRANSFORMS_ENV}'])"


def _run_in_fresh_process(*, env: dict[str, str]) -> str:
    result = subprocess.run(  # noqa: S603 - comando literal, sin shell
        [sys.executable, "-c", PRINT_ENV_CODE],
        shell=False,
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return result.stdout.strip()


def test_import_sets_msmf_hw_transforms_before_cv2() -> None:
    env = {**os.environ}
    env.pop(HW_TRANSFORMS_ENV, None)

    assert _run_in_fresh_process(env=env) == "0"


def test_import_respects_preexisting_msmf_setting() -> None:
    env = {**os.environ, HW_TRANSFORMS_ENV: "1"}

    assert _run_in_fresh_process(env=env) == "1"
