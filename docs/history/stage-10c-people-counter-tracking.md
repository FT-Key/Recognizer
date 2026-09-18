# Etapa 10c — Contador de personas: tracking + zona/línea + overlay

- **Rama:** `stage/10c-people-counter-tracking`
- **Estado:** completada
- **Objetivo:** que el contador de personas use tracking de YOLO (`model.track`) para
  asignar IDs persistentes, cuente cruces de una línea configurable (entradas/salidas)
  con una lógica de dominio pura, y dibuje un overlay dedicado (cajas con ID, línea y
  HUD con personas actuales / entradas / salidas). Una sola vía de inferencia por app.
- **Criterios de aceptación:**
  - [x] Dominio puro `core/domain/tracking.py`: `TrackedDetection` frozen, `LineAxis`,
    `CountingLine` y `LineCrossingCounter` (con debounce `confirm_frames` e `invert`),
    sin importar infraestructura.
  - [x] Puerto `ObjectTracker` (`open`/`track`/`close`) en `core/ports`.
  - [x] Adaptador `UltralyticsDetector` con `track` (fachada mapea `boxes.id`,
    `persist=True`, tracker ByteTrack); errores envueltos en `DetectorError`.
  - [x] Config `people_counter.line` (`enabled`, `axis`, `position`, `invert`,
    `confirm_frames`) + defaults en `core/constants.py` + `config.yaml`.
  - [x] Overlay dedicado en `adapters/overlay_people.py` (cajas+ID, línea, HUD).
  - [x] Runner usa tracking + contador + overlay; `ESC`/`q` vuelve al menú.
  - [x] Tests sin hardware + gate verde (lint, typecheck, pytest, check-arch).
  - [x] Revisión del reviewer aplicada; docs/STATE actualizados.

## Plan

1. Dominio: `core/domain/tracking.py` (+ `center_x`/`center_y` en `BoundingBox`).
2. Puerto `core/ports/object_tracker.py`.
3. Config: `CountingLineConfig` en `core/config.py`, constantes y `config.yaml`.
4. Adaptador: `track` en `UltralyticsDetector`/fachada + `overlay_people.py`.
5. Runner: `run_people_counter` con tracking + `LineCrossingCounter` + overlay.
6. Tests, gate completo, revisión, docs.

## Cambios (archivos)

Modificados:
- `config.yaml`: sección `people_counter.line` (enabled/axis/position/invert/confirm_frames).
- `core/config.py`: `CountingLineConfig` y `people_counter.line`.
- `core/constants.py`: `DEFAULT_LINE_POSITION`, `DEFAULT_LINE_CONFIRM_FRAMES`,
  `DEFAULT_TRACKER_CONFIG` (`bytetrack.yaml`).
- `core/domain/detection.py`: `BoundingBox.center_x` / `center_y`.
- `adapters/ultralytics_detector.py`: `track` en fachada y adaptador, mapeo de `boxes.id`
  (`persist=True`), `_map_tracked_*`; errores en `DetectorError`.
- `cli/apps/people_counter.py`: reescrito; tracking + contador + overlay, `_HudState`.
- `tests/unit/test_people_counter.py`: actualizado a tracking/contador/línea.

Nuevos:
- `core/domain/tracking.py`: `TrackedDetection`, `LineAxis`, `CountingLine`,
  `CrossingSnapshot`, `LineCrossingCounter`.
- `core/ports/object_tracker.py`: puerto `ObjectTracker`.
- `adapters/overlay_people.py`: `draw_people_overlay` (cajas+ID, línea, HUD).
- `tests/unit/test_tracking.py`, `tests/unit/test_overlay_people.py`.

## Decisiones

- Tracking siempre activo en el contador (una sola vía de inferencia: `model.track`
  hace detección + tracking). `detect` queda como capacidad genérica del puerto.
- Línea de conteo: por defecto horizontal en `position=0.5`, referencia = centro de la
  caja; `invert` decide qué sentido cuenta como entrada. `confirm_frames` (>=1) evita
  doble conteo por jitter cerca de la línea. Sentido positivo: horizontal arriba→abajo,
  vertical izquierda→derecha.
- `TrackedDetection` (frozen) compone `Detection` + `track_id`; `LineCrossingCounter` es
  estado puro con `reset`; no purga IDs (acotado por sesión, documentado).
- Adaptador usa `persist=True` y tracker ByteTrack; IDs efímeros por sesión (`close`
  descarta el modelo). Errores envueltos en `DetectorError`.
- Overlay dedicado en `adapters/overlay_people.py`, separado del runner.

## Tests y gate (resultados reales)

- `uv run lint` — OK (165 archivos).
- `uv run typecheck` — OK (140 archivos, mypy strict).
- `uv run test` — **755 passed**, 2 deselected, cobertura **96.36%**
  (`tracking.py` y `overlay_people.py` al 100%).
- `uv run check-arch` — 3/3 contratos KEPT.
- `uv run smoke --frames 30 --no-window` — pendiente de cámara real (hardware).

## Revisión (hallazgos y correcciones)

Sin bloqueantes. Menores aplicados: tipar `tracker: ObjectTracker` en el runner,
sustituir el dict con claves mágicas por `_HudState` (dataclass) y corregir el docstring
del test a 10c.

## Commits

Pendiente; lo realiza `git-ops` al cerrar la etapa (commits en
`stage/10c-people-counter-tracking` y merge `--no-ff` a `dev`).

## Pendientes / riesgos

- Calibrar `line.position`/`invert`/`confirm_frames` con cámara real.
- El HUD `Personas` cuenta solo tracks con ID: durante el warm-up del tracker puede
  mostrar 0.
- Verificación del `.exe` con YOLO/torch (bundle ~1 GB, excluido).
