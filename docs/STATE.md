# Estado — Recognizer

- **Fase actual:** etapa 2 (gestos) mergeada en `dev` con verificación manual de gestos y FPS
  pendiente; siguiente: etapa 3 (acciones locales: teclado/multimedia y comandos)
- **Rama:** `dev`
- **Actualizado:** 2026-09-12

## Hecho
- Repo git: `main` inicial, `dev`, `stage/0-setup`; remoto `FT-Key/Recognizer` configurado.
- Merge `--no-ff` de `stage/0-setup` a `dev` (b613aeb) y push de `main`/`dev` al remoto.
- uv + Python 3.12.14; dependencias runtime y dev instaladas (mediapipe 1.0.1, opencv 5,
  pydantic 2.13, pynput, pytest, ruff, mypy, import-linter).
- Core base: `Frame`, puerto `FrameSource`, `AppConfig`/`CameraConfig`, errores del dominio.
- Adaptador `OpenCVCamera` (inyectable, testeable) y CLI `smoke`.
- Modelos en `models/`: hand_landmarker.task, gesture_recognizer.task,
  blaze_face_short_range.tflite.
- Etapa 0 con gate verde: pytest 21 tests, 98% cobertura y smoke real a 29.3 FPS.
- Etapa 1 (manos): puerto `HandTracker` + `MediaPipeHandTracker` (fachada inyectable),
  `EventBus` tipado in-process + evento `HandsDetected`, `PipelineBuilder` +
  `HandDetectionProcessor`, overlay OpenCV de 21 landmarks y flag `--no-hands` en el smoke.
- Merge `--no-ff` de `stage/1-manos` a `dev` (c57e425) y push de `dev` al remoto.
- Gate de etapa 1 en verde: lint, mypy strict (38 archivos), pytest (75 tests, 98.01%),
  check-arch (3/3) y smoke real OK con 30 eventos `HandsDetected`; integración MediaPipe OK.
- Etapa 2 (gestos): `GestureRecognizer` de MediaPipe como clasificador único, puerto
  `GestureClassifier`, `GestureDetectionProcessor` + `GestureStabilizerProcessor` (N=5/M=5),
  eventos `GestureDetected`/`GestureReleased`, `GestureOverlay` y smoke con gestos por
  defecto; gate verde: 135 tests, 97.95% cobertura, mypy strict (48 archivos), check-arch 3/3.
- Documentación: arquitectura, workflow, web-plan, historial; opencode con 5 subagentes,
  2 skills y 4 comandos.

## Siguiente (etapa 3 — acciones locales)
- Acciones locales (teclado/multimedia y comandos) disparadas por eventos de gesto, con
  decoradores gated/debounced/logged.
- Entrypoint de app local (`recognizer`) además del `smoke`.

## Bloqueos / notas
- Verificación manual de `Victory`/`Open_Palm` pendiente (y FPS de etapas 1-2) en equipo
  descargado.
- Tras editar `opencode.json`, agentes, skills o comandos: reiniciar opencode.
- `uv` no está en el PATH de sesiones ya abiertas; una terminal nueva lo tendrá.
