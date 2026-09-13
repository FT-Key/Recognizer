# Estado — Recognizer

- **Fase actual:** etapa 0 completada y publicada en `dev`; siguiente: etapa 1 (manos)
- **Rama:** `dev` — la etapa 1 se trabajará en `stage/1-manos`
- **Actualizado:** 2026-09-12

## Hecho
- Repo git: `main` inicial, `dev`, `stage/0-setup`; remoto `FT-Key/Recognizer` configurado.
- Merge `--no-ff` de `stage/0-setup` a `dev` (b613aeb) y push de `main`/`dev` al remoto.
- uv + Python 3.12.14; dependencias runtime y dev instaladas (mediapipe 1.0.1, opencv 5,
  pydantic 2.13, pynput, pytest, ruff, mypy, import-linter).
- Core base: `Frame`, puerto `FrameSource`, `AppConfig`/`CameraConfig`, errores del dominio.
- Adaptador `OpenCVCamera` (inyectable, testeable) y CLI `smoke`.
- Gate estricto en verde: ruff, mypy --strict, pytest (21 tests, 98% cobertura),
  import-linter (3 contratos) y smoke real de cámara a 29.3 FPS.
- Modelos en `models/`: hand_landmarker.task, gesture_recognizer.task,
  blaze_face_short_range.tflite.
- Documentación: arquitectura, workflow, web-plan, historial; opencode con 5 subagentes,
  2 skills y 4 comandos.

## Siguiente (etapa 1 — manos)
- Adaptador MediaPipe `HandLandmarker` implementando un puerto `HandTracker`.
- EventBus tipado + `PipelineBuilder`.
- Overlay de 21 landmarks en la ventana del smoke.
- Criterio: 2 manos detectadas a 640x480 con >= 20 FPS.

## Bloqueos / notas
- Ninguno.
- Tras editar `opencode.json`, agentes, skills o comandos: reiniciar opencode.
- `uv` no está en el PATH de sesiones ya abiertas; una terminal nueva lo tendrá.
