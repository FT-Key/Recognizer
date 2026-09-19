# Fix 15b-7 — Costo de inferencia facial (modelos extra y tope de FPS)

- **Rama:** stage/15b-fix7-face-infer-cost
- **Estado:** completada
- **Objetivo:** la app facial se ponía lentísima al aparecer un rostro con la cámara del
  teléfono; acotar el costo de inferencia sin bajar resolución.
- **Criterios de aceptación:**
  - [x] Solo se cargan los modelos usados (detección + reconocimiento).
  - [x] Tope de inferencias por segundo (`max_inference_fps`, default 5; 0 = sin tope).
  - [x] Gate verde.

## Causa raíz
`FaceAnalysis` carga por defecto `detection` + `recognition` + `landmark_2d_106` +
`landmark_3d_68` + `genderage`. El detector corre siempre, pero al aparecer una cara `get()`
ejecuta los otros modelos por cara → pico de CPU; con el decode del stream del teléfono
comptiendo, se traban captura y dibujo. Además el worker infería en cada fotograma nuevo.

## Cambios (archivos)
- `adapters/insightface_recognizer.py`: `allowed_modules=["detection", "recognition"]`.
- `core/constants.py`: `DEFAULT_FACE_MAX_INFERENCE_FPS = 5.0`.
- `core/config.py`: `FaceAuthConfig.max_inference_fps`.
- `cli/apps/face_auth.py`: el worker respeta el tope por tiempo (no por frame).
- `config.yaml`: `max_inference_fps: 5.0` + notas.
- Tests: `test_insightface_recognizer.py` (módulos), config y throttle del worker.
- `docs/ARCHITECTURE.md`: nota del costo acotado.

## Decisiones
- Sin bajar resolución (pedido del usuario).
- `max_inference_fps` por tiempo (no `process_every_n_frames`, que depende del FPS de cámara);
  se conservan ambos.

## Tests y gate (resultados reales)
- `uv run lint`: OK. `uv run typecheck`: OK (187). `uv run test`: **1133 passed** (94.88%).
- `uv run check-arch`: 3/3.

## Commits
- Pendiente `git-ops`.

## Pendientes / riesgos
- Verificar con la cámara del teléfono real que el pico desaparece; subir/bajar
  `max_inference_fps` según CPU.
