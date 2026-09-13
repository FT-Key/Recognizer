# Estado — Recognizer

- **Fase actual:** etapa 3 (acciones locales) completada, publicada en `dev` con gate verde
  y smoke real; siguiente: etapa 4 (puntero virtual con suavizado y calibración)
- **Rama:** `dev` (etapa 3 mergeada)
- **Actualizado:** 2026-09-12

## Hecho
- Repo git: `main` inicial, `dev`, `stage/0-setup`; remoto `FT-Key/Recognizer` configurado.
- uv + Python 3.12.14; dependencias runtime y dev instaladas (mediapipe 1.0.1, opencv 5,
  pydantic 2.13, pynput, pytest, ruff, mypy, import-linter).
- Core base: `Frame`, puerto `FrameSource`, `AppConfig`/`CameraConfig`, errores del dominio.
- Adaptador `OpenCVCamera` (inyectable, testeable), CLI `smoke` y modelos en `models/`
  (hand_landmarker.task, gesture_recognizer.task, blaze_face_short_range.tflite).
- Etapa 0 con gate verde: pytest 21 tests, 98% cobertura y smoke real a 29.3 FPS.
- Etapa 1 (manos): puerto `HandTracker` + `MediaPipeHandTracker`, `EventBus` tipado +
  `HandsDetected`, `PipelineBuilder` + `HandDetectionProcessor` y overlay OpenCV.
- Gate de etapa 1 en verde: lint, mypy strict (38 archivos), pytest (75 tests, 98.01%),
  check-arch (3/3) y smoke real OK.
- Etapa 2 (gestos): `GestureRecognizer` de MediaPipe, puerto `GestureClassifier`,
  `GestureDetectionProcessor` + `GestureStabilizerProcessor` (N=5/M=5), eventos
  `GestureDetected`/`GestureReleased` y `GestureOverlay`.
- Gate de etapa 2 en verde: 135 tests, 97.95% cobertura, mypy strict (48 archivos),
  check-arch 3/3.
- Etapa 3 (acciones locales): `Action`/`MediaKey`/`ActionContext`, puertos `KeySender` y
  `CommandRunner`, acciones media key/hotkey/command/no-op con
  `Gated(Debounced(Logged(...)))`, dispatcher con fallback no-op, `ActionsConfig` en
  `config.yaml`, adaptadores pynput/subprocess y entrypoint `recognizer` con HUD (tecla `a`).
- Gate de etapa 3 en verde: lint, mypy strict (71 archivos), pytest (208 tests, 98.57%),
  check-arch 3/3; smoke real OK (30 fotogramas, 15.0 FPS) y app real OK con acciones.
- Merges `--no-ff` a `dev` y push: etapa 0 (b613aeb), etapa 1 (c57e425), etapa 2
  (c23da42) y etapa 3 (15e5fb9).
- Documentación: arquitectura, workflow, web-plan, historial; opencode con 5 subagentes,
  2 skills y 4 comandos.

## Siguiente (etapa 4 — puntero virtual)
- Puntero virtual con suavizado y calibración a partir de landmarks.

## Bloqueos / notas
- Verificación manual de `Victory`/`Open_Palm` pendiente (y FPS de etapas 1-2) en equipo
  descargado.
- Verificación manual de acciones reales pendiente: pulsar teclas multimedia/atajo y lanzar
  un comando descomentando el ejemplo de `config.yaml`.
- Verificaciones manuales de etapas 0-3 consolidadas en `docs/PENDING-TESTS.md`; se ejecutan
  al cerrar la etapa 4.
- Tras editar `opencode.json`, agentes, skills o comandos: reiniciar opencode.
- `uv` no está en el PATH de sesiones ya abiertas; una terminal nueva lo tendrá.
