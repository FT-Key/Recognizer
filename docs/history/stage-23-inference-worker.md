# Fix 23 — Worker genérico de inferencia (somnolencia, edad/género, privacidad)

- **Rama:** `dev` (cambios sin commitear; ver "Commits")
- **Estado:** completada
- **Objetivo:** que la cámara se vea en tiempo real en somnolencia, edad/género y desenfoque de
  privacidad con la cámara del teléfono (red), igual que la app facial: sin bloquearse
  esperando a que termine la inferencia ni acumular retraso.
- **Criterios de aceptación:**
  - [x] La inferencia de las 3 apps corre fuera del hilo de dibujo.
  - [x] El stream de la cámara de red se drena siempre (sin retraso creciente).
  - [x] Un worker reutilizable evita duplicar el patrón en cada app.
  - [x] Gate verde y verificado con cámara real (headless).

## Causa raíz

`run_camera_loop` es síncrono (leer → inferir → dibujar). Estas 3 apps corrían la inferencia
**dentro de `on_context`** (en el hilo del bucle):

- somnolencia: YOLO pose + MediaPipe Face Mesh por fotograma (~0.3-0.5 s),
- edad/género: InsightFace det + genderage (~0.3 s),
- desenfoque de privacidad: InsightFace det (~0.2 s).

Con la cámara local (búfer 1) no se notaba; con la **cámara del teléfono (WiFi)** el bucle se
quedaba dentro de la inferencia sin leer, no drenaba el stream y el retraso crecía. Es el
mismo síntoma que la app facial resolvió en la etapa 15b-5 (ver
`docs/history/stage-15b-fix5-face-async.md`).

## Cambios (archivos)

- Nuevo `cli/inference_worker.py` (`LatestInferenceWorker`): worker **genérico** que corre
  `infer(frame) -> T` sobre el último fotograma de un `LatestFrameSource` y entrega el
  resultado con `on_result`. Toma fotogramas con `wait_for_new` (sin consumir), así que salta
  los intermedios y siempre trabaja con el más nuevo.
- `cli/apps/privacy_blur.py`, `cli/apps/gender_age.py`, `cli/apps/drowsiness.py`: envuelven la
  cámara con `LatestFrameSource`, crean el worker y el bucle principal **solo dibuja** con el
  último resultado publicado:
  - privacidad: la detección publica cajas; el bucle difumina y dibuja.
  - edad/género: la estimación + suavizado corren en el worker; el bucle dibuja.
  - somnolencia: pose + face mesh + `DrowsinessDetector.update` + alerta corren en el worker;
    el bucle dibuja el esqueleto y el HUD.
- `core/constants.py`: `INFERENCE_WORKER_WAIT_TIMEOUT_SECONDS`/`_JOIN_TIMEOUT_SECONDS`.
- `docs/ARCHITECTURE.md`: la sección de latencia pasa a "apps con inferencia lenta" y
  documenta el worker genérico.
- Tests: `tests/unit/test_inference_worker.py` (procesa el último, throttle, error) y los
  runners de las 3 apps (fuente dirigida que corre la inferencia en `read()`).

## Mediciones (headless, cámara real, CPU 4 núcleos)

| App | Antes (síncrono) | Después (worker) |
|---|---|---|
| Desenfoque privacidad | ~5 FPS | **32.7 FPS** |
| Edad y género | ~2-3 FPS | **28.0 FPS** |
| Somnolencia | ~2 FPS | **30.1 FPS** |
| OCR (ya decoplado) | — | 30.6 FPS |

## Decisiones

- **Worker genérico** (`LatestInferenceWorker`) para no duplicar el patrón en 3 apps; la facial
  y el OCR conservan sus workers propios (`_RecognitionWorker`, `_OCRWorker`) por su lógica
  específica (matching, ROI, cambio de fotograma).
- El resultado se publica como objeto inmutable (tuplas/dataclasses) y se asigna a un estado
  simple: no hace falta lock para el caso de un solo worker.
- La alerta sonora de somnolencia se dispara en el worker (I/O) y el bucle solo dibuja.
- La privacidad difumina con las últimas cajas: si el rostro se mueve entre inferencias, el
  marco va con un fotograma de retraso (compromiso aceptable frente a congelar la vista).

## Tests y gate (resultados reales)

- `uv run lint`: OK. `uv run typecheck`: OK (252 archivos). `uv run test`: **1575 passed**
  (93.97%). `uv run check-arch`: 3/3.
- Verificado con cámara real headless: las 3 apps devuelven exit 0 a ~28-33 FPS.

## Commits

- Pendiente `git-ops` (todo el trabajo de las etapas 20/22/23 sigue sin commitear en `dev`).

## Pendientes / riesgos

- Verificar con la cámara del teléfono real que desaparece el retraso en las 3 apps.
- La privacidad puede dejar ver parcialmente un rostro que se mueve rápido (cajas con un
  fotograma de retraso); si molesta, subir la frecuencia de inferencia o bajar `det_size`.
