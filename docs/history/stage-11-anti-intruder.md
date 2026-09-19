# Etapa 11 — Anti-intrusos (zona + alerta)

- **Rama:** `stage/11-anti-intruder`
- **Estado:** completada
- **Objetivo:** app que detecta personas dentro de una zona configurable y dispara una
  alerta (visual en el overlay + sonora del sistema) mientras haya intrusos, reutilizando
  el tracking YOLO de la etapa 10c. Una sola vía de inferencia (`model.track`).
- **Criterios de aceptación:**
  - [x] Dominio puro `core/domain/intrusion.py`: `IntrusionZone` (normalizada y validada),
    `ZoneIntrusionMonitor` (debounce `confirm_frames`/`release_frames`, tracks que
    desaparecen se liberan) y `IntrusionSnapshot` (`active`, `intruder_ids`, `count`).
  - [x] Config `anti_intruder` (`model_path`, `min_confidence`, `target_label`, `zone` y
    `alert`) + defaults en `core/constants.py` + `config.yaml`.
  - [x] Puerto `AlertSink` (`notify`/`close`) en `core/ports`.
  - [x] Adaptadores: `adapters/alert_sound.py` (`SystemSoundAlert` con winsound y fachada
    inyectable + `SilentAlert`) y `adapters/overlay_intrusion.py` (zona verde/roja, cajas
    de intrusos en rojo, HUD y banner ALERTA).
  - [x] Runner `cli/apps/anti_intruder.py`; `ESC`/`q` vuelve al menú; alerta edge-triggered
    con repetición configurable.
  - [x] Catálogo `implemented=True` para `anti_intruder`; `resolve_runner` con import
    perezoso; `config.yaml apps.enabled`.
  - [x] Tests sin hardware + gate verde (lint, typecheck, pytest, check-arch).
  - [x] Revisión del reviewer sin bloqueantes; docs/STATE actualizados.

## Plan

1. Dominio: `core/domain/intrusion.py`.
2. Config: `AntiIntruderConfig`/`IntrusionZoneConfig`/`IntrusionAlertConfig` + constantes + YAML.
3. Puerto `AlertSink` y adaptadores de alerta/overlay.
4. Runner, catálogo y menú.
5. Tests, gate, revisión y docs.

## Cambios (archivos)

Nuevos:
- `src/recognizer/core/domain/intrusion.py`: `IntrusionZone` (rectángulo normalizado 0..1
  validado; `contains` por centro de la caja), `IntrusionSnapshot` (`active`,
  `intruder_ids`, `count`) y `ZoneIntrusionMonitor` (debounce `confirm_frames`/
  `release_frames`; los tracks no vistos cuentan como fuera; purga los tracks liberados).
- `src/recognizer/core/ports/alert_sink.py`: puerto `AlertSink` (`notify`/`close`).
- `src/recognizer/adapters/alert_sound.py`: `SystemSoundAlert` (winsound tras una fachada
  inyectable; degrada a no-op/log ante `ImportError`/`OSError`/`RuntimeError`) y
  `SilentAlert` (Null Object).
- `src/recognizer/adapters/overlay_intrusion.py`: `draw_intrusion_overlay` (zona verde/roja,
  cajas de intrusos en rojo, HUD `Zona: N intrusos` y banner `ALERTA: INTRUSO EN ZONA`).
- `src/recognizer/cli/apps/anti_intruder.py`: runner `run_anti_intruder`; alerta
  edge-triggered que se repite según `alert.repeat_seconds`; `ESC`/`q` vuelve al menú.
- Tests: `tests/unit/test_intrusion.py`, `tests/unit/test_overlay_intrusion.py`,
  `tests/unit/test_anti_intruder.py`.

Modificados:
- `src/recognizer/core/config.py`: `IntrusionZoneConfig`, `IntrusionAlertConfig`,
  `AntiIntruderConfig` y `AppConfig.anti_intruder`.
- `src/recognizer/core/constants.py`: defaults `DEFAULT_INTRUSION_*`.
- `src/recognizer/core/ports/object_detector.py`: Protocol estructural `DetectorConfig`
  (`model_path`, `min_confidence`).
- `src/recognizer/adapters/ultralytics_detector.py`: acepta `DetectorConfig`
  (reutilizable por contador y anti-intrusos).
- `src/recognizer/core/domain/app.py`: `anti_intruder` con `implemented=True`.
- `src/recognizer/cli/menu.py`: rama `AppId.ANTI_INTRUDER` con import perezoso.
- `config.yaml`: sección `anti_intruder` (zona por defecto x 0.25-0.75, y 0.4-0.9;
  confirm 3, release 5; alerta activa con `repeat_seconds` 2.0) y
  `apps.enabled.anti_intruder: true`.
- Ajustes en `tests/unit/test_app_domain.py`, `test_menu.py`, `test_menu_gui.py`,
  `test_people_counter.py` (nueva app implementada y config estructural).

## Decisiones

- Pertenencia a la zona por el centro de la caja (más estable que el solape de área).
- Debounce de confirmación (`confirm_frames`) y liberación (`release_frames`) para evitar
  alertar por ruido del tracker o por un objeto que solo cruza.
- Alerta sonora con `winsound` aislada por una fachada inyectable (tests sin audio real)
  y desactivable con `alert.enabled: false`.
- Alerta edge-triggered: se dispara al comenzar la intrusión y se repite cada
  `repeat_seconds` mientras dure (`0` = una sola vez).
- Reutilización del detector vía `DetectorConfig` estructural, sin acoplar el adaptador a
  una app concreta (contador y anti-intrusos comparten `UltralyticsDetector`).
- Zona deshabilitada (`zone.enabled: false`) = solo cajas, sin monitor ni alerta.

## Tests y gate (resultados reales)

- `uv run lint` — OK (173 archivos).
- `uv run typecheck` — OK (148 archivos, mypy strict).
- `uv run test` — **812 passed**, 2 deselected, cobertura **96.57%**.
- `uv run check-arch` — 3/3 KEPT (121 archivos, 519 dependencias).
- `uv run smoke --frames 30 --no-window` — pendiente de cámara real.

## Revisión (hallazgos y correcciones)

Sin bloqueantes. Menores aplicados: purgar los tracks liberados en `ZoneIntrusionMonitor`
(acota el estado de la sesión) y capturar `OSError`/`RuntimeError` en `WinsoundFacade`
(además de `ImportError`).

## Commits

Cambios de la etapa en el árbol de trabajo sobre `stage/11-anti-intruder` (HEAD en
`1e8a5a6`, merge de 10c); pendientes de commit al cierre.

## Pendientes / riesgos

- Calibrar con cámara real `anti_intruder.zone` (x/y, `confirm_frames`/`release_frames`) y
  `alert.repeat_seconds`.
- `uv run smoke` y verificación del `.exe` (YOLO/torch, bundle ~1 GB) pendientes.
- Los `.md` `docs/DESKTOP-EXPLICADO.md` y `docs/DESKTOP-SIMPLIFICADO.md` quedan sin
  trackear (ajenos a la etapa).
