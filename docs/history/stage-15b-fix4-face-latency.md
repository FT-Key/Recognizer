# Fix 15b-4 — Latencia de la app facial con cámara del teléfono

- **Rama:** stage/15b-fix4-face-latency
- **Estado:** completada
- **Objetivo:** eliminar el retraso creciente (segundos) y la lentitud del preview en la app
  facial con cámaras lentas (enlace móvil / del teléfono), sin afectar a las demás apps.
- **Criterios de aceptación:**
  - [x] La captura usa búfer mínimo (frame más reciente, sin acumular atraso).
  - [x] `face_auth.det_size` y `face_auth.process_every_n_frames` configurables.
  - [x] Frame skipping: la vista se redibuja cada frame; la inferencia se reutiliza.
  - [x] Gate verde.

## Causa raíz
La app facial es la única con inferencia (InsightFace CPU) más lenta que la cámara. OpenCV
acumulaba fotogramas en su búfer, así que cada `read()` devolvía un frame viejo y el retraso
crecía hasta segundos. Las otras apps (MediaPipe/YOLO) procesan más rápido que la cámara y no
acumulan.

## Cambios (archivos)
- `adapters/camera_opencv.py` + `core/constants.py`: `CAP_PROP_BUFFERSIZE = 1`
  (`DEFAULT_CAPTURE_BUFFER_SIZE`).
- `core/ports/face_recognizer.py`: el protocolo de config exige `det_size`.
- `adapters/insightface_recognizer.py`: la fachada usa `config.det_size`.
- `core/config.py`: `FaceAuthConfig.det_size` y `FaceAuthConfig.process_every_n_frames`.
- `cli/apps/face_auth.py`: throttle de inferencia (reutiliza la última observación y redibuja
  cada frame) en enrolamiento y login.
- `config.yaml`: `det_size` y `process_every_n_frames` con notas de calibración.
- Tests: búfer mínimo en `test_camera_opencv.py`; defaults/validación en `test_face_menu_config.py`.

## Decisiones
- Búfer 1 es el arreglo principal: acota la latencia a una inferencia (no crece con el tiempo).
- `process_every_n_frames` (default 1) permite aliviar CPUs lentas manteniendo la vista fluida;
  la detección se reutiliza y no se duplican muestras de enrolamiento.
- `det_size` (default 640) permite bajarlo a 320 para acelerar; es config, no código.

## Tests y gate (resultados reales)
- `uv run lint`: OK. `uv run typecheck`: OK (183). `uv run test`: **1123 passed** (94.68%).
- `uv run check-arch`: 3/3.

## Commits
- Pendiente `git-ops`.

## Pendientes / riesgos
- `CAP_PROP_BUFFERSIZE` no lo soportan todos los backends; con `process_every_n_frames`/`det_size`
  queda el ajuste alternativo. Calibrar con cámara real.
