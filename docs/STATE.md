# Estado — Recognizer

- **Fase actual:** etapa 1 (manos) mergeada en `dev`; criterio FPS pendiente de verificación manual
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
- Documentación: arquitectura, workflow, web-plan, historial; opencode con 5 subagentes,
  2 skills y 4 comandos.

## Siguiente (etapa 2 — gestos)
- `GestureClassifier` + `GestureStabilizer` + eventos de gesto + overlay en el smoke.
- Criterio de aceptación a definir; verificar también el FPS pendiente de la etapa 1.

## Bloqueos / notas
- Criterio "2 manos a 640x480 >= 20 FPS" pendiente de verificar en equipo descargado
  (carga externa del 83-94% durante la etapa).
- Tras editar `opencode.json`, agentes, skills o comandos: reiniciar opencode.
- `uv` no está en el PATH de sesiones ya abiertas; una terminal nueva lo tendrá.
