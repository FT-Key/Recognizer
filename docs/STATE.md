# Estado — Recognizer

- **Fase actual:** etapa 5 (gestos personalizados) completada y mergeada en `dev`; siguiente:
  etapa 6 (acciones script, bloqueante/no bloqueante)
- **Rama:** `dev` (etapa 5 mergeada con `--no-ff`)
- **Actualizado:** 2026-09-13

## Hecho
- Repo git: `main` inicial, `dev`, `stage/0-setup`; remoto `FT-Key/Recognizer` configurado.
- uv + Python 3.12.14; dependencias runtime y dev instaladas (mediapipe 1.0.1, opencv 5,
  pydantic 2.13, pynput, pytest, ruff, mypy, import-linter).
- Core base: `Frame`, puerto `FrameSource`, `AppConfig`/`CameraConfig`, errores del dominio.
- Adaptador `OpenCVCamera` (inyectable, testeable), CLI `smoke` y modelos en `models/`.
- Etapa 0 con gate verde: pytest 21 tests, 98% cobertura y smoke real a 29.3 FPS.
- Etapa 1 (manos): puerto `HandTracker` + `MediaPipeHandTracker`, `EventBus` tipado +
  `HandsDetected`, `PipelineBuilder` + `HandDetectionProcessor` y overlay OpenCV.
- Etapa 2 (gestos): `GestureRecognizer` de MediaPipe, puerto `GestureClassifier`,
  `GestureDetectionProcessor` + `GestureStabilizerProcessor` (N=5/M=5), eventos
  `GestureDetected`/`GestureReleased` y `GestureOverlay`.
- Etapa 3 (acciones locales): `Action`/`MediaKey`/`ActionContext`, puertos `KeySender` y
  `CommandRunner`, acciones media key/hotkey/command/no-op con
  `Gated(Debounced(Logged(...)))`, dispatcher con fallback no-op, `ActionsConfig` en
  `config.yaml`, adaptadores pynput/subprocess y entrypoint `recognizer` con HUD (tecla `a`).
- Etapa 4 (puntero virtual): `PointerPosition`/`PointerCalibration` y evento
  `PointerMoved`; `PointerDetectionProcessor` (landmark 8 con gesto estable) y
  `PointerMover` con gate compartido; Strategy de suavizado `none`/`ema` (alpha 0.35);
  puerto `MouseController` + `PynputMouseController`; `PointerConfig`/`ActiveZoneConfig`
  en `config.yaml` (zona 0.2-0.8, `mirror_x`), `PointerOverlay` y flag `--no-pointer`.
- Gate de etapa 4 en verde: lint (109 archivos), mypy strict (83), pytest (290 tests,
  98.61%), check-arch 3/3 y smoke real OK (30 fotogramas, 4.6 FPS con CPU cargada).
- Etapa 5 (gestos personalizados): vocabulario abierto (`GestureId` + `GestureCatalog`)
  en vez del enum cerrado; reglas geométricas de landmarks en `config.yaml`
  (`gestures.rules`, `rules_priority`, `rule_thresholds`) con `LandmarkRuleProcessor`;
  `gestures.custom_labels` para modelos MediaPipe custom; `config.yaml` con ejemplos
  comentados. Gate verde: pytest 342 tests, 98.72%, mypy 87, check-arch 3/3, smoke 13.7 FPS.
- Merges `--no-ff` a `dev` y push: etapa 0 (b613aeb), etapa 1 (c57e425), etapa 2
  (c23da42), etapa 3 (15e5fb9) y etapa 4 (4da3e35).
- Documentación: arquitectura, workflow, web-plan, historial; opencode con 5 subagentes,
  2 skills y 4 comandos.

## Siguiente (etapa 6 — acciones script)
- Acción `script` (`.py`, `.ps1`, `.bat/.cmd`, `.sh`) con puerto `ScriptRunner`, modo
  bloqueante y no bloqueante, y paso del contexto del gesto.

## Bloqueos / notas
- Verificaciones manuales de etapas 0-5 (gestos, acciones reales, puntero, reglas de
  landmarks y FPS) consolidadas en `docs/PENDING-TESTS.md`; las ejecuta el usuario
  cuando pueda.
- Tras editar `opencode.json`, agentes, skills o comandos: reiniciar opencode.
- `uv` no está en el PATH de sesiones ya abiertas; una terminal nueva lo tendrá.
