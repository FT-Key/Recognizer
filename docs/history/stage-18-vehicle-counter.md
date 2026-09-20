# Etapa 18 — Conteo de autos

- **Rama:** stage/18-vehicle-counter
- **Estado:** en curso
- **Objetivo:** App de conteo de vehículos que cruzan una línea con YOLO + ByteTrack,
  reutilizando `LineCrossingCounter` y `UltralyticsDetector` del contador de personas.
- **Criterios de aceptación:**
  - `AppId.VEHICLE_COUNTER` marcado `implemented=True` en el catálogo.
  - Runner `run_vehicle_counter` en `cli/apps/vehicle_counter.py` con import perezoso en `menu.py`.
  - `VehicleCounterConfig` en `core/config.py` con sección `vehicle_counter` en `config.yaml`.
  - Overlay con cajas+ID, línea de conteo y HUD (vehículos actuales, entradas, salidas).
  - Gate completo verde: lint, typecheck, test (≥80%), check-arch.

## Plan

1. Constantes en `core/constants.py` (`DEFAULT_VEHICLE_*`).
2. `VehicleCounterConfig` en `core/config.py` + campo en `AppConfig`.
3. `AppId.VEHICLE_COUNTER` → `implemented=True` en `core/domain/app.py`.
4. Overlay `adapters/overlay_vehicle.py` (reutiliza lógica de `overlay_people`).
5. Runner `cli/apps/vehicle_counter.py`.
6. Import perezoso en `cli/menu.py`.
7. Sección `vehicle_counter` en `config.yaml`.
8. Tests unitarios en `tests/unit/test_vehicle_counter.py`.
9. Gate completo.

## Cambios (archivos)

- `src/recognizer/core/constants.py` — constantes `DEFAULT_VEHICLE_*`
- `src/recognizer/core/config.py` — `VehicleCounterConfig` + `AppConfig.vehicle_counter`
- `src/recognizer/core/domain/app.py` — `implemented=True` para `VEHICLE_COUNTER`
- `src/recognizer/adapters/overlay_vehicle.py` — overlay nuevo
- `src/recognizer/cli/apps/vehicle_counter.py` — runner nuevo
- `src/recognizer/cli/menu.py` — rama perezosa `VEHICLE_COUNTER`
- `config.yaml` — sección `vehicle_counter`
- `tests/unit/test_vehicle_counter.py` — tests unitarios

## Decisiones

- `target_label: "car"` por defecto (COCO: car, truck, bus, motorcycle disponibles).
- Reutiliza `LineCrossingCounter` y `UltralyticsDetector` sin modificarlos.
- Overlay propio (`overlay_vehicle.py`) para no acoplar colores/HUD al de personas.
- No se agrega dominio nuevo: el dominio de tracking ya cubre el caso de uso.

## Tests y gate (resultados reales)

⚠️ **PENDIENTE — ejecutar antes del merge:**
```
uv run lint        # ya pasó en sesión de implementación
uv run typecheck   # ya pasó en sesión de implementación
uv run pytest tests/unit/ -x -q --tb=short
uv run check-arch
```
Tests nuevos: `tests/unit/test_vehicle_counter.py` (17 casos).
Tests existentes actualizados:
- `test_app_domain.py::test_implemented_apps_are_in_order` — agrega `VEHICLE_COUNTER`
- `test_menu.py::test_run_menu_skips_coming_soon_without_runner` — cambia opción `"9"` → `"10"`
- `test_menu_gui.py::test_build_menu_rows_reflects_states_and_descriptions` — lista dinámica

## Revisión (hallazgos y correcciones)

_pendiente — ejecutar `/stage-review` con el agente `reviewer` antes del merge_

## Commits

_pendiente_

## Pendientes / riesgos

- Calibrar `target_label` con cámara real (puede necesitar `"truck"` o lista).
- FPS con modelo nano en CPU: medir con `uv run smoke`.
