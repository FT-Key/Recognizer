# -*- mode: python ; coding: utf-8 -*-
"""Especificacion de PyInstaller para Recognizer (version de escritorio).

Uso (desde la raiz del repo):
    uv run pyinstaller --noconfirm --clean packaging/recognizer.spec
    # o simplemente:
    uv run python scripts/build_exe.py

Se usa modo *onedir* (carpeta), no onefile: MediaPipe carga DLLs nativas y
memory-mapea los modelos .task, y extraerlos a un temporal en cada arranque
(onefile) es lento e inestable.

La configuracion (config.yaml), los modelos (models/) y los scripts de usuario
(scripts/actions/) NO se incrustan: scripts/build_exe.py los copia junto al
ejecutable para que el usuario pueda editarlos sin recompilar.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

PROJECT_ROOT = Path(SPECPATH).parent  # type: ignore[name-defined]  # noqa: F821
SRC_DIR = PROJECT_ROOT / "src"

datas = []
binaries = []
hiddenimports = []

# MediaPipe carga modelos y binarios nativos por ruta en tiempo de ejecucion:
# hay que recolectar datos, binarios y submodulos explicitamente.
for package in ("mediapipe",):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

hiddenimports += collect_submodules("pynput")
hiddenimports += collect_submodules("websocket")

a = Analysis(  # noqa: F821
    [str(PROJECT_ROOT / "packaging" / "entrypoint.py")],
    pathex=[str(SRC_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # NO excluir matplotlib: mediapipe.tasks.python.vision.drawing_utils lo
    # importa a nivel de modulo y su ausencia rompe la carga de MediaPipe.
    # NO excluir tkinter: pynput_mouse._default_screen_size() lo importa para
    # resolver el tamano de pantalla del puntero; sin el, el puntero falla.
    excludes=["pandas", "pytest", "ruff", "mypy"],
    noarchive=False,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Recognizer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Recognizer",
)
