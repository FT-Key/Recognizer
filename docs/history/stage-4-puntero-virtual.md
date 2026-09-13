# Etapa 4 — Puntero virtual con suavizado y calibración

- **Rama:** stage/4-puntero-virtual
- **Estado:** completada
- **Objetivo:** mover el puntero del sistema siguiendo la punta del índice cuando el gesto
  de activación (`Pointing_Up`) está confirmado, con calibración de zona activa y suavizado
  configurable; sin mover el ratón cuando el gesto no está activo.
- **Criterios de aceptación:**
  - `PointerConfig` en `config.yaml`/pydantic: `enabled`, `activation_gesture` (default
    `Pointing_Up`), `mirror_x`, `smoothing` (`none`|`ema`) con `alpha` y `active_zone`
    (`x_min`/`x_max`/`y_min`/`y_max`), validada (min < max, 0..1).
  - Dominio: `PointerPosition` normalizado (0..1) y `PointerCalibration` (zona activa +
    espejo + recorte); evento `PointerMoved`.
  - Suavizado como Strategy (`PointerSmoothing`): `NoSmoothing` y `ExponentialSmoothing`
    con reinicio al perder el gesto; factory desde config.
  - `PointerDetectionProcessor` en el pipeline tras el estabilizador: usa el landmark 8
    (punta del índice) de la mano que hace el gesto de activación y publica `PointerMoved`.
  - Puerto `MouseController` + adaptador `PynputMouseController` (controller y tamaño de
    pantalla inyectables); el movimiento real lo hace `PointerMover`, que respeta el
    `ActionGate` compartido y no cae si el sistema falla (`ActionError` -> warning).
  - Overlay del puntero (cruz + coordenadas) visible con ventana.
  - CLI: flag `--no-pointer`; tecla `a` alterna acciones y puntero; resumen final con el
    contador `PointerMoved`.
  - Gate verde: lint, typecheck, test (cobertura >= 80%) y check-arch.
  - Verificación manual (cámara + humano) documentada en `docs/PENDING-TESTS.md`.

## Plan
1. Dominio y evento: `PointerPosition`, `PointerCalibration`, `PointerMoved`; landmark 8.
2. Puerto `MouseController`; Strategy de suavizado (`core/pointer/smoothing.py`).
3. `PointerDetectionProcessor` (core/pipeline) + campo `pointer` en `FrameContext`.
4. `PointerMover` (core/pointer) suscrito a `PointerMoved` y gated.
5. Config pydantic (`PointerConfig`, `ActiveZoneConfig`) y `config.yaml`.
6. Adaptador `PynputMouseController` (pynput + tamaño de pantalla) y `PointerOverlay`.
7. Bootstrap y CLI `recognizer` (`--no-pointer`, gate compartido, stats).
8. Tests automatizados, gate, revisión y cierre.

## Cambios (archivos)
- Nuevos: `core/domain/pointer.py` (`SmoothingKind`, `PointerPosition`,
  `PointerCalibration` con validación min<max y recorte 0..1),
  `core/ports/mouse_controller.py` (puerto `MouseController`), `core/pointer/smoothing.py`
  (`PointerSmoothing` con `NoSmoothing`/`ExponentialSmoothing` y factory),
  `core/pointer/mover.py` (`PointerMover`), `core/pipeline/pointer_detection.py`
  (`PointerDetectionProcessor`) y `adapters/pynput_mouse.py` (`PynputMouseController`).
- Modificados: `core/domain/hand.py` (landmark 8, punta del índice),
  `core/domain/events.py` (`PointerMoved`), `core/pipeline/context.py` (campo `pointer`),
  `core/config.py` (`PointerConfig` + `ActiveZoneConfig`), `core/constants.py` (defaults y
  logger del puntero), `adapters/overlay_opencv.py` (`PointerOverlay`), `bootstrap.py`
  (`build_pipeline(pointer=)`, `build_action_bindings(gate=)`, `build_pointer_mover`),
  `cli/app.py` (`--no-pointer`, gate compartido, stats y resumen) y `config.yaml` (sección
  `pointer`).

## Decisiones
- Activación solo con el gesto estable (default `Pointing_Up`, configurable): al perderse
  se detiene el puntero y se resetean el suavizado y el overlay.
- Zona activa 0.2-0.8 proyectada sobre toda la pantalla, con recorte 0..1; `mirror_x: true`
  por defecto para la vista selfie de la cámara.
- Suavizado como Strategy: `none` (Null Object) o `ema` (alpha 0.35 por defecto), con reset
  al perder el gesto y selección desde config.
- Un único `ActionGate` compartido por acciones y puntero (tecla `a`); `--no-actions` y
  `--no-pointer` son flags independientes.
- HUD: "Acciones: ON/OFF" cuando hay acciones y "Puntero: ON/OFF" cuando solo hay puntero.
- `PynputMouseController` inyecta controller y tamaño de pantalla (testeable sin hardware)
  y difiere el import de tkinter; si el sistema falla, el `ActionError` se loguea y el loop
  sigue.
- `PointerCalibration.__post_init__` valida min<max (lanza `ConfigError`).
- El smoke no construye el puntero ni mueve el ratón; solo lo hace `recognizer`.

## Tests y gate (resultados reales)
- `uv run lint`: OK (ruff check + format, 109 archivos).
- `uv run typecheck`: OK (mypy strict, 83 archivos).
- `uv run test`: 290 passed + 2 deselected, cobertura 98.61% (umbral 80%); 208 -> 290 tests
  (82 nuevos): 5 archivos nuevos (`test_pointer_domain`, `test_pointer_smoothing`,
  `test_pointer_detection`, `test_pointer_mover`, `test_pynput_mouse`) y 4 modificados.
- `uv run check-arch`: 3/3 contratos KEPT.
- `uv run smoke --frames 30 --no-window`: OK real (30 fotogramas, 4.6 FPS con CPU cargada
  y 0 manos); el smoke no mueve el ratón.
- Nota: el FPS de esta sesión (4.6) se midió con CPU cargada; la comparación con etapas
  previas queda para la verificación manual.

## Revisión (hallazgos y correcciones)
- Veredicto del `reviewer`: "apto para merge sin bloqueantes". 6 hallazgos menores.
- Corregidos: (a) HUD y etiqueta del gate correctos cuando solo hay puntero; (b) recorte
  del overlay a `(width-1)`; (c) validación de calibración en `__post_init__`; (d) import
  diferido de tkinter en el adaptador; y refuerzo de tests del cableado del CLI y de las
  esquinas del overlay.
- Restante (no bloqueante): esta actualización de la documentación.

## Commits
- `3b9be78` feat(puntero): puntero virtual con suavizado y calibracion.
- `898c859` docs(history): cierre de la etapa 4 puntero virtual.
- `4da3e35` merge: etapa 4 - puntero virtual (`--no-ff` a `dev`).
- Base de la rama: `943c056` (`docs: plan de verificaciones pendientes para el cierre de la etapa 4`).

## Pendientes / riesgos
- Verificaciones manuales (movimiento real, sentido, calibración, suavizado, gate,
  `--no-pointer` y FPS) en `docs/PENDING-TESTS.md`; las ejecuta el usuario.
- Comparar `uv run smoke --frames 120 --no-window` (no mueve el ratón) con etapas previas
  bajo carga similar.
- Los comandos configurados se ejecutan de verdad: el ejemplo sigue comentado en
  `config.yaml`.
