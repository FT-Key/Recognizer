# Fix 15b-5 — Captura asíncrona + worker de inferencia (app facial)

- **Rama:** stage/15b-fix5-face-async
- **Estado:** completada
- **Objetivo:** eliminar el retraso creciente y la lentitud de la app facial con cámaras de red
  (teléfono/enlace móvil) sin tocar las demás apps, y dejar documentado el patrón.
- **Criterios de aceptación:**
  - [x] `LatestFrameSource` drena la cámara en un hilo y expone el último fotograma.
  - [x] Worker de inferencia: el dibujo va a ritmo de cámara; la inferencia corre aparte.
  - [x] `det_size` 320 por defecto en config + `process_every_n_frames`.
  - [x] Solo la app facial usa el patrón; el resto intacto.
  - [x] Documentado en `docs/ARCHITECTURE.md` (diferencia y cómo aplicarlo a otras apps).
  - [x] Gate verde.

## Causa raíz
`run_camera_loop` es single-thread: lee → infiere → dibuja. La inferencia facial (~2-5 FPS)
bloquea la lectura, no drena el stream de la cámara de red y el retraso crece hasta segundos;
la app de enlace avisa "calidad de red deficiente". Las demás apps infieren rápido y no
acumulan. `CAP_PROP_BUFFERSIZE=1` no cubre el búfer de red del emisor.

## Cambios (archivos)
- Nuevo `adapters/latest_frame_source.py`: hilo de captura, `read()` (copia, espera al nuevo),
  `wait_for_new(version)` (no consume), `release()` limpio.
- `cli/apps/face_auth.py`: `_RecognitionWorker` (inferencia en hilo, estado bajo lock) y uso de
  `LatestFrameSource` en enrolamiento y login; el bucle principal solo dibuja.
- `core/constants.py`: timeouts del drenado/worker.
- `config.yaml`: `det_size: 320` + notas; `process_every_n_frames`.
- `docs/ARCHITECTURE.md`: sección "Latencia y desacople de inferencia (app facial)" con la
  diferencia vs otras apps y cómo aplicar el patrón.
- Tests: `tests/unit/test_latest_frame_source.py`, `tests/unit/test_face_worker.py`.

## Decisiones
- Se aplica **solo a la app facial** (única con inferencia más lenta que la cámara); las demás
  quedan igual y el patrón está documentado para cuando haga falta.
- `read()` devuelve copia para que el overlay no compita con la lectura del worker.
- `process_every_n_frames` ahora lo aplica el worker (antes el bucle); `det_size` baja a 320.

## Tests y gate (resultados reales)
- `uv run lint`: OK. `uv run typecheck`: OK (186). `uv run test`: **1130 passed** (94.65%).
- `uv run check-arch`: 3/3.

## Revisión (hallazgos y correcciones)
- Reviewer: requiere cambios → aplicados.
- Bloqueante: `release()` liberaba la cámara con el hilo de captura vivo → `OpenCVCamera`
  serializa `read`/`release` con un lock y el drenado atrapa excepciones y termina.
- Mayor: el worker solo capturaba `RecognizerError` → ahora captura cualquier `Exception`
  (envuelve en `FaceRecognizerError`) y no muere en silencio.
- Mayor: `stop()` con timeout podía dejar el worker escribiendo tras cerrar → se comprueba
  `stop` antes de `_process` y se avisa si no termina a tiempo.
- Menores: `RECOGNIZING_TEXT` como constante; `_write_login_session` fuera del lock.

## Commits
- Pendiente `git-ops`.

## Pendientes / riesgos
- Verificar con la cámara del teléfono real que desaparece el aviso de red y el retraso.
- Si alguna otra app muestra latencia, aplicar el mismo patrón (documentado en ARCHITECTURE).
