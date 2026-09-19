# Etapa 10c-fix2 — Contador: eje vertical por defecto

- **Rama:** `stage/10c-fix2-vertical-default`
- **Estado:** completada
- **Objetivo:** que el contador cuente el paso lateral frente a la cámara (izquierda ↔
  derecha). Con la línea horizontal, atravesar el cuadro de lado a lado no cruza la
  línea (el centro Y no cambia de lado) y el HUD se quedaba en 0 entradas/salidas.
- **Criterios de aceptación:**
  - [x] Default de `people_counter.line.axis` en `vertical` (código y `config.yaml`).
  - [x] Tests ajustados sin perder cobertura del eje horizontal.
  - [x] Docs manuales actualizadas al nuevo default.
  - [x] Gate verde y merge a `dev`.

## Plan

1. `config.yaml` y `CountingLineConfig.axis` a `LineAxis.VERTICAL`.
2. Tests: default esperado en `test_tracking.py`; eje explícito en el helper del
   runner (`test_people_counter.py`) para seguir cubriendo el cruce horizontal.
3. Docs: `PENDING-TESTS.md`, `STATE.md`, history e índice.
4. Gate, cierre y merge.

## Cambios (archivos)

- `config.yaml`: `people_counter.line.axis: vertical` + comentario del default.
- `src/recognizer/core/config.py`: `CountingLineConfig.axis` por defecto `VERTICAL`.
- `tests/unit/test_tracking.py`: el default esperado es `VERTICAL`.
- `tests/unit/test_people_counter.py`: `_app_config_with_line` acepta `axis`
  (por defecto `HORIZONTAL` para no cambiar la intención de esos tests) + import de
  `LineAxis`.
- `docs/PENDING-TESTS.md`, `docs/STATE.md`, `docs/history/index.md`, este history.

## Decisiones

- Se cambia el default (no solo la config local) porque el paso lateral es el caso
  típico de un contador frente a una cámara; el eje horizontal sigue disponible con
  `axis: horizontal` (arriba abajo = entradas).
- Semántica con vertical: izquierda → derecha = `Entradas`, derecha → izquierda =
  `Salidas` (con `invert` se intercambian). La banda muerta y la purga no cambian.

## Tests y gate (resultados reales)

- `uv run lint` — OK (183 archivos).
- `uv run typecheck` — OK (158 archivos, mypy strict).
- `uv run test` — **973 passed, 2 deselected**, cobertura **96.75%**
  (`core/domain/tracking.py` y `adapters/overlay_people.py` al 100%).
- `uv run check-arch` — 3/3 contratos KEPT.
- `uv run smoke --frames 30 --no-window` — OK (30 fotogramas, 7.2 FPS, 1 mano).

## Revisión (hallazgos y correcciones)

Sin reviewer formal (cambio mínimo de default + ajuste de tests): auto-revisión del
orquestador contra `AGENTS.md` (core intacto, sin `Any`, sin mágicos, keyword-only).
Sin bloqueantes.

## Commits

- `e974d79` `fix(10c): eje vertical por defecto en la linea de conteo`
- (docs de la etapa en el commit siguiente de la rama; merge a `dev` al cierre)

## Pendientes / riesgos

- Verificar con cámara real que el paso lateral suma `Entradas`/`Salidas`.
