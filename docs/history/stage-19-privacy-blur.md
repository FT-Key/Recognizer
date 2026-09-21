# Etapa 19 — Desenfoque de privacidad

- **Rama:** stage/19-privacy-blur
- **Estado:** completada
- **Objetivo:** difuminar caras en vivo (anonimización) sin guardar imágenes ni identidades.
- **Criterios de aceptación:**
  - `AppId.PRIVACY_BLUR` con `implemented=True` ("Difumina las caras en vivo con InsightFace").
  - Detección con InsightFace `buffalo_s` (solo módulo `detection`, sin embeddings).
  - Una sola vía de inferencia, import perezoso, `ESC`/`q` vuelve al menú.
  - `PrivacyBlurConfig` + sección `privacy_blur`; dominio puro en `core`.
  - Gate completo verde y corrida real con cámara.

## Plan
1. Dominio puro `core/domain/privacy.py` (`PixelRect`, `face_blur_regions`, `effective_blur_kernel`).
2. Puerto `core/ports/face_detector.py` + error `FaceDetectorError`.
3. Adaptador `adapters/insightface_detector.py` (reutiliza helpers de `insightface_recognizer`).
4. Overlay `adapters/overlay_privacy.py` (`blur_faces` + HUD "Rostros difuminados").
5. Runner `cli/apps/privacy_blur.py` + rama perezosa en `cli/menu.py`.
6. Config, catálogo, tests y gate.

## Cambios (archivos)
- Nuevos: `core/domain/privacy.py`, `core/ports/face_detector.py`,
  `adapters/insightface_detector.py`, `adapters/overlay_privacy.py`,
  `cli/apps/privacy_blur.py`, `tests/unit/test_privacy_blur.py` (44 casos).
- Modificados: `core/constants.py` (`DEFAULT_PRIVACY_*`; se eliminó `DEFAULT_PRIVACY_TARGET_LABELS`),
  `core/config.py` (`PrivacyBlurConfig` + campo `privacy_blur`, omitido en el trabajo parcial previo),
  `core/domain/app.py`, `core/errors.py` (`FaceDetectorError`), `adapters/insightface_recognizer.py`
  (helpers `split_model_path`/`create_analysis` públicos), `cli/menu.py`, `config.yaml` y tests
  `test_app_domain.py`, `test_menu.py`, `test_insightface_recognizer.py`, `test_menu_gui.py`.

## Decisiones
- `buffalo_s` con `modules=("detection",)`: sin embeddings ni identidades.
- Se descartó `yolo26n.pt`: COCO no tiene clase `face` ni `license plate`.
- Patentes: pendientes; requieren detector propio (no hay preentrenado).
- `effective_blur_kernel` normaliza a kernel impar acotado; `margin_ratio` 0.15 por defecto.
- Fix `test_menu_gui.py`: la fila 5 (FACE_AUTH) colgaba; ahora presiona la 11 (FALL_DETECTOR).

## Tests y gate (resultados reales)
- `uv run lint` OK; `uv run typecheck` OK (227 archivos, mypy strict).
- `uv run test`: **1413 passed**, cobertura **94.33%** (umbral 80%).
- `uv run check-arch`: 3/3 KEPT.
- `uv run smoke --frames 30 --no-window`: 8.3 FPS (cámara real).
- Corrida real: buffalo_s + cámara, 10 fotogramas, 4.9 FPS, 1 rostro, exit 0.
- Queda verde también el gate pendiente de la etapa 18 (suite + check-arch).

## Revisión (hallazgos y correcciones)
- Reviewer: apta. 3 hallazgos menores aplicados:
  1. HUD cuenta regiones difuminadas (`blurred`), no caras detectadas.
  2. Tests de fallo de `open()`, cajas degeneradas y validación de `PixelRect`.
  3. Documentación actualizada.

## Commits
- `078a7e2` feat(19): desenfoque de privacidad (InsightFace det + blur).
- `c96d5b7` merge(19): desenfoque de privacidad desde stage/19-privacy-blur (dev, push OK).

## Pendientes / riesgos
- Patentes sin soporte (requiere detector propio).
- Calibrar `det_size`, `min_confidence` y `blur_strength` con cámara real.
- Coste CPU (~4.9 FPS); evaluar `process_every_n_frames` a futuro.
- Merge a `dev` y push pendientes (git-ops).
