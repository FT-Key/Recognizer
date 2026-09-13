# Etapa 8 — Gestos compuestos (menús por mano) + script de video

- **Rama:** stage/8-gestos-compuestos
- **Estado:** completada
- **Objetivo:** permitir gestos compuestos: con una mano el comportamiento normal y con
  dos manos, la izquierda sostiene un gesto modificador que abre una lista de comandos y
  la derecha elige la opción. Primer menú (`Replay`) y primer script: volver el video que
  se reproduce en Chrome al inicio (tecla `0`).

- **Criterios de aceptación:**
  - Con una sola mano el comportamiento es el actual (acciones globales; `Pointing_Up`
    mueve el puntero). ✅
  - Con dos manos, izquierda `Pointing_Up` + derecha una opción del menú, se ejecuta la
    opción y no su acción global (`consume_trigger`). No se mueve el cursor. ✅
  - `actions.menus` permite varias listas y opciones (solo config). ✅
  - `gestures.swap_handedness` corrige la lateralidad si MediaPipe la invierte. ✅
  - Script `scripts/actions/video_start.ps1` que detecta el video en reproducción de
    Chrome, lo enfoca y pulsa `0`. ✅ (verificación manual pendiente)
  - Tests, config.yaml, README, overlay simple y gate verde. ✅

## Plan
1. Config `actions.menus` + `gestures.swap_handedness` con validación fail-fast.
2. `HandGestureTracker` + resolución de menú en el dispatcher (consume trigger).
3. Puntero desactivado con más de una mano; overlay de menú.
4. Script `video_start.ps1` (GSMTC → ventana Chrome activa → clic al video → `0`).
5. Tests y gate; revisión; docs; merge.

## Cambios (archivos)
- `core/domain/hand.py`: helper `other_hand` (swap de lateralidad; `UNKNOWN` intacto).
- `core/actions/menus.py` (nuevo): `Menu`, `MenuMatch`, `HandGestureTracker`,
  `find_menu_match` (core puro, sin efectos).
- `core/actions/dispatcher.py`: resuelve menús con estado por mano, `consume_trigger`,
  `GestureReleased`, y anti-repetición por mano disparadora (`_last_match`).
- `core/config.py`: `MenuConfig`, `ActionsConfig.menus`, `GestureConfig.swap_handedness`,
  validación de referencias de menús contra el catálogo.
- `core/pipeline/pointer_detection.py` + `core/constants.py`: el puntero no se activa con
  más de una mano visible (`POINTER_MAX_VISIBLE_HANDS`).
- `adapters/mediapipe_gesture_classifier.py`: aplica `swap_handedness` (reutiliza
  `other_hand`).
- `adapters/overlay_opencv.py`: `MenuOverlay` (nombre del menú activo y opciones).
- `bootstrap.py`: helper `_wrap_action`, `ActionBindings.menus`, `build_pipeline(menus=...)`.
- `cli/app.py`: gate de acciones por `mappings` o `menus`; dispatcher con menús;
  suscripción a `GestureReleased`.
- `config.yaml`: `swap_handedness` y sección `menus.Replay` (izquierda `Pointing_Up` +
  derecha `Victory` → `video_start.ps1`).
- `scripts/actions/video_start.ps1` (nuevo) y `.gitignore` (log del script).

## Decisiones
- La resolución del menú vive en el dispatcher con estado por mano (evita problemas de
  orden de eventos del pipeline) y dispara una sola vez por combinación; solo se rearma
  al liberar la mano disparadora.
- Puntero solo con una mano visible.
- Script v1 en PowerShell (sin dependencias) por simplicidad de uso; CDP/extensión queda
  como mejora futura de fiabilidad.
- "El video más cercano" = ventana de Chrome con título coincidente o la más reciente.

## Tests y gate (resultados reales)
- `uv run test`: **442 passed**, 2 deselected, cobertura **98.94%** (umbral 80%).
- `uv run pytest -m integration --no-cov`: **2 passed**, 442 deselected.
- `uv run lint`: ruff check OK; ruff format OK (130 archivos).
- `uv run typecheck`: mypy strict OK (99 archivos).
- `uv run check-arch`: **3/3** contratos KEPT.
- `uv run smoke --frames 30 --no-window`: **Smoke OK**, 30 fotogramas, 13.3 FPS.
- Tests nuevos: `test_menus.py`; ampliados `test_action_dispatcher.py` (menú, consumo,
  no repetición, parpadeo del modificador, error), `test_action_config.py`,
  `test_pointer_detection.py`, `test_mediapipe_gesture_classifier.py`,
  `test_overlay_opencv.py`, `test_bootstrap.py`, `test_app_cli.py`.

## Revisión (hallazgos y correcciones)
- Hallazgo **mayor** corregido: `_last_match` se limpiaba con el `GestureReleased` de
  cualquier mano, de modo que un parpadeo del modificador repetía la acción sin liberar la
  opción; ahora se recuerda la mano disparadora y solo se rearma al liberarla (test de
  parpadeo añadido).
- Menores corregidos: `$netTask.Wait` con timeout en el script (evita cuelgue de WinRT);
  el script aborta sin enviar la tecla si no logra poner Chrome al frente; se elimina el
  mapa de swap duplicado reutilizando `other_hand` del dominio.
- Menor documentado: si el gesto de la derecha se confirma antes de sostener el
  modificador, puede ejecutar también su acción global (comentado en `config.yaml`).

## Commits
_(pendiente)_

## Pendientes / riesgos
- Verificación manual con cámara: calibración de `swap_handedness`, menú y script `0`.
- La entrega de la tecla `0` depende del foco; se mitiga con clic previo al video.
