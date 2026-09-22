# Etapa 21 — Edad y genero (`gender_age`)

- **Rama:** stage/21-gender-age
- **Estado:** completada
- **Objetivo:** app del launcher que estima edad y genero de cada rostro en vivo con
  InsightFace (`buffalo_s`, modulos `detection` + `genderage`) y los muestra en el overlay.
- **Criterios de aceptacion:**
  - `AppId.GENDER_AGE` con `implemented=True` y `apps.enabled.gender_age` en `config.yaml`.
  - Runner `cli/apps/gender_age.py` con import perezoso en `menu.resolve_runner`; `ESC`/`q`
    vuelve al menu.
  - Una sola via de inferencia (deteccion + genderage, sin embeddings); no carga modelos
    de otras apps.
  - Dominio puro (`FaceGender`, `FaceAttributes`, `AgeGenderSmoother` con mediana de edad
    y voto mayoritario de genero por IoU) + puerto `FaceAttributeEstimator`.
  - Overlay con caja, etiqueta `M/F/? ~edad` y HUD `Rostros: N`.
  - Config pydantic `GenderAgeConfig` y seccion `gender_age` en `config.yaml`.
  - Tests unitarios sin hardware; gate completo verde.

## Plan

1. Dominio: `core/domain/face_attributes.py` (enums/objeto de valor/IoU/suavizador).
2. Puerto: `core/ports/face_attributes.py`; error `FaceAttributeError` en `core/errors.py`.
3. Constantes y config (`core/constants.py`, `core/config.py`, `config.yaml`).
4. Adaptador InsightFace: `adapters/insightface_attributes.py` (fachada + estimador).
5. Overlay: `adapters/overlay_gender_age.py`.
6. Runner: `cli/apps/gender_age.py` + rama perezosa en `cli/menu.py`.
7. Catalogo: `implemented=True` en `core/domain/app.py`.
8. Tests y gate; revision; documentacion; merge a `dev`.

## Decisiones

- Se implementa la etapa 21 (edad/genero) a pedido explicito del usuario; la etapa 20
  (caidas) queda pendiente en el roadmap.
- Se reutiliza `models/buffalo_s` (ya usado por facial/privacidad): `genderage` es un
  modulo mas del pack, no requiere dependencia nueva.
- Suavizado en dominio puro (mediana de edad + voto mayoritario de genero, emparejando
  caras por IoU) para evitar el parpadeo tipico del estimador; `smoothing_window: 1`
  desactiva el efecto (valor crudo).
- `genderage` de InsightFace devuelve genero como clase 0/1 (0 = femenino, 1 = masculino
  segun `Face.sex`); el mapeo vive en el adaptador, no en el dominio.

## Cambios (archivos)

- `src/recognizer/core/domain/face_attributes.py` (nuevo)
- `src/recognizer/core/ports/face_attributes.py` (nuevo)
- `src/recognizer/adapters/insightface_attributes.py` (nuevo)
- `src/recognizer/adapters/overlay_gender_age.py` (nuevo)
- `src/recognizer/cli/apps/gender_age.py` (nuevo)
- `src/recognizer/core/errors.py`, `core/constants.py`, `core/config.py`,
  `core/domain/app.py`, `cli/menu.py`, `config.yaml`

## Tests y gate (resultados reales)

- `uv run lint` OK (ruff check + 258 archivos formateados).
- `uv run typecheck` OK (mypy strict, 233 archivos).
- `uv run test`: **1472 passed, 3 deselected**, cobertura total **94.68%**
  (total antes 94.48%): `face_attributes.py` 96%, `insightface_attributes.py` 99%,
  `overlay_gender_age.py` 100%, `ports/face_attributes.py` 100%.
- `uv run check-arch`: 3/3 contratos KEPT.
- Tests nuevos: `tests/unit/test_gender_age.py` con **55 tests** (dominio/IoU/suavizador,
  config, catálogo/menú lazy, overlay, fachada con fakes, estimador, runner headless).
- `uv run smoke --frames 30 --no-window`: 8.0 FPS (cámara real, 1 mano en cuadro).

## Revisión (hallazgos y correcciones)

- Reviewer: apta con cambios (solo menores):
  - (a) doc "supere el umbral" vs `>=` — corregido a "iguale o supere"
    en `face_attributes.py`.
  - (b) off-by-one del suavizador (slots nuevos nacían con `misses=1`) —
    corregido añadiendo los slots nuevos a `used` en `update`; tests siguen verdes.
  - (c) riesgo compartido con etapa 19 (no bloqueante): una caja en píxeles totalmente
    fuera del cuadro en un eje podría colapsar con `_clamp01` y lanzar `ConfigError`
    en `FaceBox`; se deja como pendiente documentado, sin tocar el patrón de
    privacidad en esta etapa.

## Commits

- `c4918ae` feat(21): edad y genero (gender_age).
- `59af9c9` test(21): tests de edad y genero + catalogo/menu.
- `45cb564` docs(21): historial, STATE, ROADMAP e indice de la etapa.

## Pendientes / riesgos

- Calibrar `gender_age.det_size` / `min_confidence` / `smoothing_window` con cámara real.
- La edad es aproximada (desvíos en menores y luz pobre); el género es binario según
  el modelo.
- Coste CPU similar a privacidad; smoke con cámara real pendiente.
- Etapa 20 (caídas) sigue pendiente en el roadmap.
