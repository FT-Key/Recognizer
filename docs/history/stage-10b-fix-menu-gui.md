# Etapa 10b-fix — Menú GUI + salida a menú

- **Rama:** stage/10b-fix-menu-gui
- **Estado:** completada
- **Objetivo:** (1) que ESC/q y la X salgan de cualquier app OpenCV de vuelta al menú, (2) menú principal en ventana emergente tkinter/ttk con fallback a consola.
- **Criterios de aceptación:**
  1. ESC/q sale de cualquier app OpenCV de vuelta al menú (con foco en la ventana). ✅
  2. La X de la ventana OpenCV sale a menú (aun sin foco de teclado). ✅
  3. Menú principal en ventana emergente tkinter/ttk; al elegir app y cerrarse, vuelve al menú. ✅
  4. Fallback a consola con `--no-gui` o sin display (`ImportError`/`TclError`). ✅
  5. Sin imports pesados al abrir el menú (sin cv2/MediaPipe/YOLO/torch). ✅
  6. Gate verde (`lint`, `typecheck`, `test`, `check-arch`). ✅

## Plan
1. `runtime.py`: traer ventana al frente + detectar X como salida a menú.
2. `menu_gui.py` nuevo: ventana tkinter/ttk con `build_menu_rows` pura + `run_gui_menu` con `withdraw/deiconify`.
3. `menu.py`/`app.py`: `run_launcher(use_gui, gui_runner)` + flag `--no-gui` + fallback a consola.
4. `constants.py`/`spec`: constantes de ventana + hiddenimport `menu_gui`.
5. Tests con dobles (FakeRoot/Listbox, sin display) + gate completo.

## Cambios (archivos)
- `src/recognizer/cli/runtime.py` (+26): `_bring_to_front` (namedWindow + toggle TOPMOST) y `_window_closed` (X vía `WND_PROP_VISIBLE`); break por ESC/q/X.
- `src/recognizer/cli/menu_gui.py` (nuevo): `MenuRow` frozen, `build_menu_rows` pura, `run_gui_menu` (tkinter perezoso, `tk_factory` inyectable, X/ESC/Salir → 0).
- `src/recognizer/cli/menu.py` (+39/-? ): `GuiRunner`, `_default_gui_runner` perezoso, `run_launcher(use_gui, gui_runner)` con fallback en `ImportError`/`TclError`.
- `src/recognizer/cli/app.py` (+9): flag `--no-gui` → `run_launcher(use_gui=False)`.
- `src/recognizer/core/constants.py` (+3): `WINDOW_TOPMOST_ENABLED/DISABLED`, `WINDOW_MIN_VISIBLE_VALUE`.
- `packaging/recognizer.spec` (1 línea): hiddenimport `recognizer.cli.menu_gui` (torch sigue excluido).
- Tests: `tests/unit/test_menu_gui.py` (nuevo, 10 tests), `test_menu.py` (+100), `test_runtime.py` (+99).
- Stat tracked (`git diff --stat HEAD`): 8 archivos, 283 inserciones(+), 8 borrados(-); más 2 nuevos sin track (`menu_gui.py`, `test_menu_gui.py`) y 2 docs (`DESKTOP-*.md`, este history).

## Decisiones
- TOPMOST toggle + break por X tolerante a `cv2.error`: `setWindowProperty`/`getWindowProperty` varían por backend; se suprime/retorna `False` para no romper el loop.
- tkinter stdlib perezoso, cero deps: import solo dentro de `run_gui_menu`/`run_launcher`; el menú nunca carga cv2/MediaPipe/YOLO/torch (test `test_opening_menu_does_not_import_heavy_deps`).
- `gui_runner` inyectable tras el cuelgue de `test_menu` detectado en el gate: el runner real abre `mainloop`; los tests inyectan dobles vía `gui_runner`/`tk_factory` sin display.
- Fallback consola con `--no-gui`/`TclError`: `use_gui=False` va directo a `run_menu`; `TclError` (lance el runner real o un doble) cae a consola con log "sin display".

## Tests y gate (resultados reales)
- `uv run test`: **692 passed, 2 deselected, cobertura 96.17%** (mínimo 80% superado).
- `uv run lint`: ruff check + format OK — **158 files already formatted**.
- `uv run typecheck`: mypy --strict OK — **no issues found in 134 source files**.
- `uv run check-arch`: import-linter OK — **3 kept, 0 broken** (110 files, 465 deps).
- Re-verificados por docs-writer en esta sesión (no citados del test-writer).

## Revisión (hallazgos y correcciones)
- Sin bloqueantes.
- 4 infos dejadas como pendientes: (1) verificar ESC/q+X con cámara real y foco; (2) verificar ventana tkinter con display real y retorno tras app; (3) ramas GUI no cubiertas por dobles (p. ej. `KeyboardInterrupt` en `mainloop`); (4) `.exe` con `menu_gui` pendiente de prueba en Windows (torch sigue excluido).

## Commits
- Sin commits (documentación no commitea por instrucción; `git-ops` cierra la etapa).

## Pendientes / riesgos
- Usuario verifica manual: ESC/q+X y ventana del menú con cámara real (`PENDING-TESTS.md`).
- Verificación del `.exe` con torch/YOLO pendiente (bundle ~1 GB, excluido del spec).
- Riesgo bajo: backends OpenCV sin `WND_PROP_VISIBLE` → la X no detecta, pero ESC/q sigue funcionando.
