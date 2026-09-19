# Fix 15b-3 — `session.json` interpretado como rostro (no se podía reabrir la app)

- **Rama:** stage/15b-fix2-face-ux (commit sobre el fix anterior)
- **Estado:** completada
- **Objetivo:** tras el login se crea `data/faces/session.json`; el repositorio lo tomaba como un
  id facial (`"session"`) y `list_all()` lanzaba `FaceRepositoryError: face_id invalido`,
  rompiendo la reapertura del submenú facial.
- **Criterios de aceptación:**
  - [x] `session.json`/`index.json` y cualquier JSON sin formato `F-0001` se ignoran.
  - [x] `list_all`, `next_id` y `find_by_name` siguen funcionando con `session.json` presente.
  - [x] Índices legados con ids inválidos se filtran.
  - [x] Gate verde.

## Causa raíz
`FileFaceRepository._known_ids` listaba todos los `*.json` del store y solo excluía `index`.
El `session.json` del login se colaba como id `"session"` y `_read_face_file` lo rechazaba.

## Cambios (archivos)
- `adapters/file_face_repository.py`: `_known_ids` filtra por `FACE_ID_PATTERN` tanto los ids del
  índice como los archivos en disco.
- `cli/face_menu_gui.py`: `_store_is_empty` captura también `RecognizerError` (defensivo).
- `tests/unit/test_face_repository.py`: +2 tests (session.json ignorado; índice legado con id inválido).

## Decisiones
- El formato de id facial es la única fuente de verdad: todo lo demás en el directorio se ignora.
- Sin migración destructiva: el índice se reescribe limpio en el próximo `save()`.

## Tests y gate (resultados reales)
- `uv run lint`: OK. `uv run typecheck`: OK (183). `uv run test`: **1121 passed** (94.60%). `uv run check-arch`: 3/3.

## Commits
- Pendiente `git-ops`.

## Pendientes / riesgos
- Si el `index.json` del usuario ya contiene `"session"`, queda filtrado en lectura y se limpia al
  guardar la próxima cara.
