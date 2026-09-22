# Fix 23 — Latencia y rendimiento del OCR (CPU y cámara del teléfono)

- **Rama:** `dev` (cambios sin commitear; ver "Commits")
- **Estado:** completada
- **Objetivo:** que el OCR en vivo no congele la ventana ni acumule retraso, tanto con la
  cámara local (CPU) como con la cámara de red del teléfono (alta resolución por WiFi), y
  que las actualizaciones de texto lleguen en ~1-3 s en vez de ~10 s.
- **Criterios de aceptación:**
  - [x] La inferencia OCR corre fuera del hilo de dibujo (la ventana va a ritmo de cámara).
  - [x] El stream de la cámara de red se drena siempre (sin retraso creciente).
  - [x] Coste por inferencia acotado (recorte de ROI y fotograma reducidos).
  - [x] No se reprocesa una ROI sin cambios.
  - [x] Todo configurable en `config.yaml`; gate verde.

## Causa raíz

Dos problemas encadenados:

1. **Single-thread + inferencia lenta:** `run_camera_loop` es síncrono (leer → inferir →
   dibujar). EasyOCR en CPU tarda **~10-11 s por fotograma** en un recorte 1024x576 (idiomas
   `en`+`es`, CRAFT a lienzo 2560). El bucle quedaba bloqueado ese tiempo: la ventana mostraba
   una imagen, se congelaba, y recién ~10 s después venía la siguiente.
2. **Cámara de red:** con la cámara del teléfono (más resolución y por WiFi) el bucle tampoco
   drenaba el stream, así que se acumulaba retraso (mismo síntoma que sufrió la app facial en
   la etapa 15b-4/15b-5).

## Cambios (archivos)

- `cli/apps/ocr_reader.py`:
  - `_OCRWorker`: hilo de inferencia que toma el último fotograma de `LatestFrameSource`
    (`wait_for_new`, sin consumir) y entrega las cajas al bucle de dibujo.
  - El runner envuelve la cámara con `LatestFrameSource` (drenado continuo) y el bucle
    principal **solo dibuja**.
  - Reducción del fotograma a `max_frame_width` antes de convertir/detectar; las cajas se
    reescalan al fotograma original (`_rescale_boxes`) para el overlay.
  - Detección de cambios: firma 32x32 en grises de la ROI; si no cambió (diferencia media <
    `change_threshold`) se conservan las cajas y no se corre OCR.
  - `max_inference_fps` y `process_every_n_frames` acotan la frecuencia de inferencia.
- `adapters/easyocr_engine.py`: el recorte de la ROI se reduce a `max_width` antes de
  `readtext`; se fijan `paragraph=False`, `batch_size=1`, `mag_ratio` y `canvas_size`; las
  cajas se reescalan a coordenadas del fotograma.
- `core/config.py` + `core/constants.py`: `OCRReaderConfig` gana `max_width`,
  `max_frame_width`, `canvas_size`, `mag_ratio`, `change_threshold` y `max_inference_fps`.
- `config.yaml`: sección `ocr_reader` con los nuevos valores y notas de calibración.
- `docs/ARCHITECTURE.md`: la sección de latencia pasa de "app facial" a "apps facial y OCR"
  (patrón común documentado).
- Tests: `tests/unit/test_ocr_reader.py` (worker asíncrono, cambio de fotograma, downscale y
  reescalado de cajas, defaults de config).

## Mediciones (CPU, 4 núcleos, sin GPU)

| Configuración | Tiempo por inferencia |
|---|---|
| EasyOCR default (canvas 2560) | ~11.3 s |
| `canvas_size=1280`, `mag_ratio=1.0` | ~10.0 s |
| + recorte reducido a 640 | ~3.6 s |
| + recorte a 480 | ~2.3 s |
| + recorte a 320 | ~1.5 s |

El display del bucle principal se mantiene a ~26-29 FPS con el worker corriendo una
inferencia pesada de 2 s, incluso a 1080p y 4K (medido con una fuente fake).

## Decisiones

- Se aplica el **mismo patrón que la app facial** (`LatestFrameSource` + worker), como indica
  `docs/ARCHITECTURE.md`; no se toca `core`.
- El coste de EasyOCR escala con los píxeles: la palanca principal es achicar el recorte
  (ROI y `max_width`), no la frecuencia.
- `change_threshold` evita reprocesar una escena estática (hoja quieta) cada pocos segundos.
- `max_frame_width=1280` ayuda con cámaras de red de alta resolución sin afectar a la cámara
  local de 1280x720.
- La ROI es la mejor palanca de calidad/velocidad: una ROI más chica es más rápida **y**
  detecta mejor el texto pequeño.

## Tests y gate (resultados reales)

- `uv run lint`: OK. `uv run typecheck`: OK (250 archivos). `uv run test`: **1572 passed**
  (93.96%). `uv run check-arch`: 3/3.
- Verificado con cámara real headless (`run_ocr_reader`, exit 0).

## Commits

- Pendiente `git-ops` (todo el trabajo de la etapa 23 sigue sin commitear en `dev`).

## Pendientes / riesgos

- Calibrar `ocr_reader.*` con la cámara del teléfono real: `max_frame_width`, `max_width`,
  `change_threshold`, `min_confidence` y `roi_*`.
- Si EasyOCR sigue lento en CPU, evaluar un adaptador RapidOCR/PP-OCR (onnxruntime ya es
  dependencia); el puerto `OCREngine` permite intercambiarlo sin tocar el resto.
