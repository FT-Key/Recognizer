# Etapa 15a — Enrolamiento + login facial (archivos locales, base distribuible)

- **Rama:** stage/15a-face-enroll-login
- **Estado:** completada (implementación + gate verdes; pendiente merge `git-ops`)
- **Objetivo:** registrar cara con nombre + ID automático F-0001 y logueo solo con rostro; archivos locales <100 usuarios; puertos listos para DB futura y login distribuido.
- **Criterios de aceptación:**
  - [x] Enrolar pide nombre, guía 5 ángulos (frente/izq/der/arriba/abajo) + distancia, guarda embedding medio.
  - [x] ID secuencial F-0001 persistente en `data/faces/index.json`.
  - [x] Login saluda `Bienvenido <nombre> <id>` con debounce; desconocido = `Desconocido`.
  - [x] Una sola vía InsightFace CPU; menú perezoso; ESC/q vuelve al menú.
  - [x] Gate verde: lint, typecheck, pytest 1033 passed (94.63%), check-arch 3/3.

## Plan
1. Dominio `face.py` + puertos `FaceRecognizer/FaceRepository` + adaptadores + runner + config/menú.
2. Tests unitarios con dobles; gate; review; docs; merge a dev.

## Cambios (archivos)
- Nuevos: `core/domain/face.py`, `core/ports/face_recognizer.py`, `core/ports/face_repository.py`, `adapters/insightface_recognizer.py`, `adapters/file_face_repository.py`, `adapters/overlay_face.py`, `cli/apps/face_auth.py`, `tests/unit/test_face_{domain,repository,overlay,menu_config}.py`.
- Editados: `core/domain/app.py` (FACE_AUTH implemented), `cli/menu.py`, `core/constants.py`, `core/config.py` (FaceAuthConfig), `config.yaml`, `pyproject.toml` (+insightface/onnxruntime, forbidden), `scripts/download_models.py` (buffalo_s), `packaging/recognizer.spec`, `core/errors.py`, tests viejos de menú actualizados a FACE_AUTH disponible.

## Decisiones
- Sin DB ahora: `FileFaceRepository` (`data/faces/`); `FaceRepository` es el seam para futura `DbFaceRepository` (SQLite→Postgres) y login distribuido (compartir `store_dir` o réplica + mismo `match_threshold`).
- InsightFace `buffalo_s` CPU una sola vía; `assess_capture` usa ancho de caja como proxy de distancia (0.25–0.55) + sharpness; 5 pasos con prompts en español; overlay vintage (verde/ámbar/rojo).
- Login edge-triggered con `LoginDebouncer` (confirm 3 / release 5).

## Tests y gate (resultados reales)
- `uv run lint`: OK (194 archivos). `uv run typecheck`: OK (169). `uv run test`: **1033 passed** (94.63%). `uv run check-arch`: 3/3. `uv run recognizer --list-apps`: facial `[disponible]`.
- Cobertura baja solo en `insightface_recognizer.py` (37%, requiere modelo real) — aceptado, sin hardware en unit.

## Revisión (hallazgos y correcciones)
- Reviewer: **apta para merge**.
- Mayores corregidos: path-traversal en `FileFaceRepository` (saneado de nombres/rutas dentro de `store_dir`) y permisos restrictivos `chmod 0700` en `data/faces/`.

## Commits
- Pendiente `git-ops`: commits en `stage/15a-face-enroll-login`, merge `--no-ff` a `dev` y push (base `dev` en `594f9af`; a fecha de cierre no hay commits nuevos en la rama, cambios sin commitear verificados con `git status`).

## Pendientes / riesgos
- Descargar `buffalo_s` (`uv run python scripts/download_models.py`) y calibrar `match_threshold`/`min_face_sharpness` con cámara real; smoke facial headless pendiente.
- `.exe` con insightface/onnxruntime sin verificar (bundle crece); `data/faces/` excluido del bundle, documentar backup.
- Roles/permisos (IdentityProvider/PolicyEngine) quedan para 15b.
