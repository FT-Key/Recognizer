# Etapa 10b — Contador de personas: detección + conteo (YOLO)

- **Rama:** `stage/10b-people-counter`
- **Estado:** completada
- **Objetivo:** app del launcher que cuenta personas por fotograma con YOLO
  preentrenado, sin tracking (eso es 10c): detección + conteo + HUD.
- **Criterios de aceptación:**
  - [x] Dominio puro de detecciones + conteo (`BoundingBox`/`Detection` frozen,
    `count_people`), sin importar infraestructura desde `core`.
  - [x] Puerto `ObjectDetector` (`open`/`detect`/`close`) + adaptador
    `UltralyticsDetector` con carga perezosa e import diferido.
  - [x] Config `people_counter:` en `config.yaml` (`PeopleCounterConfig` +
    defaults en `core/constants.py`).
  - [x] Runner `run_people_counter` registrado con import perezoso; `ESC`/`q`
    vuelve al menú; `people_counter: true` en `apps.enabled`.
  - [x] Tests sin hardware + gate verde (lint, typecheck, pytest, check-arch).
  - [x] Revisión del reviewer aplicada; `.spec` sin bundle torch documentado.

## Plan

1. Dominio `core/domain/detection.py` + puerto `core/ports/object_detector.py`
   (+ `DetectorError`).
2. Config (`PeopleCounterConfig`, constantes, `config.yaml`) y catálogo
   (`implemented=True`).
3. Adaptador `UltralyticsDetector` con fachada inyectable + runner
   `cli/apps/people_counter.py` + registro perezoso en `menu.resolve_runner`.
4. Tests (`tests/unit/test_people_counter.py`), gate completo, revisión y docs.

## Cambios (archivos)

Modificados (`git diff --stat HEAD`: 12 archivos, +652/−12):
`config.yaml`, `packaging/recognizer.spec`, `pyproject.toml`, `uv.lock`,
`src/recognizer/cli/menu.py`, `src/recognizer/core/config.py`,
`src/recognizer/core/constants.py`, `src/recognizer/core/domain/app.py`,
`src/recognizer/core/errors.py`, `tests/unit/test_app_domain.py`,
`tests/unit/test_menu.py`, `docs/history/index.md`.
Nuevos (untracked): `src/recognizer/core/domain/detection.py`,
`src/recognizer/core/ports/object_detector.py`,
`src/recognizer/adapters/ultralytics_detector.py`,
`src/recognizer/cli/apps/people_counter.py`,
`tests/unit/test_people_counter.py`, este history.
(No relacionados con la etapa, sin tocar: `docs/DESKTOP-EXPLICADO.md`,
`docs/DESKTOP-SIMPLIFICADO.md`.)

## Decisiones

- Modelo `yolo26n.pt` (nano YOLO26, ~5.3 MB, CPU): clase `person` (COCO);
  autodescarga de Ultralytics junto al repo (`models/` por defecto, no se
  commitea) vía `model_path` de config. Verificado `names == {0: 'person', …}`.
- Conteo directo por fotograma sin `EventBus` (el tracking con `model.track`
  llega en 10c); el runner dibuja cajas + HUD `Personas: N` en `on_context`.
- Fachada `ObjectDetectorFacade` inyectable (`facade_factory`): el detector se
  testea con dobles, sin torch/YOLO instalado en tests.
- Hallazgo de API: `Boxes` no es iterable ni tiene `Box`; se indexa por fila
  (`boxes[i]` → `Boxes` de 1 fila con `xyxyn` (1,4), `conf` (1,), `cls` (1,)).
  `YOLO` se importa desde `ultralytics.models.yolo.model` (el `__init__` usa
  `__getattr__` perezoso y mypy no lo ve); `ignore_missing_imports` para
  `ultralytics`/`torch`, que además entran al contrato import-linter de `core`.
- `packaging/recognizer.spec` solo añade el hiddenimport del runner: NO hace
  `collect_all("ultralytics")` (torch haría el bundle de ~1 GB).

## Tests y gate (resultados reales)

- `uv run lint`: OK (checks passed, 156 archivos formateados).
- `uv run typecheck`: OK (132 archivos, sin errores, modo strict).
- `uv run test`: **675 passed, 2 deselected, cobertura 96.17%** (mínimo 80%).
  `tests/unit/test_people_counter.py` cubre dominio (cajas/conteo/validación),
  config, adaptador con fachada fake + mapeo real de `Boxes`, menú/catálogo y
  runner headless con cámara/detector falsos (bucle real + HUD dibujado).
- `uv run check-arch`: 3/3 contratos OK (108 archivos, 453 dependencias).
- Smoke con cámara real: pendiente de ejecución manual (ver PENDING-TESTS).

## Revisión (hallazgos y correcciones)

- Bloqueante corregido: la fachada capturaba `Exception` genérico; ahora
  captura `(OSError, RuntimeError, ValueError)` y envuelve en `DetectorError`
  con `from exc` (`adapters/ultralytics_detector.py`, `open` y `detect`).
  El `except Exception` que queda en `run_people_counter` es guarda de borde
  CLI (log + retorno 1, no tumba el launcher).
- Bajas no bloqueantes → pendientes: verificación del `.exe` con YOLO/torch y
  calibración de `min_confidence` con cámara real.

## Commits

Sin commits aún: trabajo en working tree de `stage/10b-people-counter`
(sobre el merge 10a `c8c8b9f`, ya en `dev`). NO commitear (a pedido).

## Pendientes / riesgos

- Verificar `.exe` con YOLO (torch fuera del bundle a propósito).
- Calibrar `min_confidence` (defecto 0.5) con la cámara real.
- 10c: tracking (`model.track`), zona/línea y overlay dedicado.

## Fix post-etapa — GUI del launcher inyectable (rama `stage/10b-fix-menu-gui`)

- Bloqueante del test-writer: `test_run_launcher_uses_default_config_when_missing`
  colgaba porque `run_launcher()` con `use_gui=True` abría Tk real (`mainloop`).
- Fix solo en `src/recognizer/cli/menu.py`: `run_launcher(*, list_only=False,
  use_gui=True, gui_runner: GuiRunner | None = None)` donde `GuiRunner =
  Callable[[AppRunRequest, AppsConfig, AppCatalog | None], int]`; `None`
  delega en `_default_gui_runner` (menu gráfico real, import perezoso).
- Decisión: `TclError`/`ImportError` caen al menú de consola tanto si los lanza
  el runner real como un doble inyectado (contrato en el docstring).
- `cli/app.py` sin cambios (`--no-gui` ya propaga `use_gui=False` por keyword).
- Tests no tocados (los ajusta test-writer). Sin commits.
