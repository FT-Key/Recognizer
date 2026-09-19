# Etapa 15c — Gestión de usuarios, accesos y fotos

- **Rama:** stage/15c-users-access
- **Estado:** completada
- **Objetivo:** corregir el submenú facial (botones Login/Logout según sesión y selector de rol
  visible), guardar una foto en el enrolamiento y la primera foto reconocida en cada login,
  y añadir paneles de administración (usuarios CRUD y accesos) con permisos por rol.
- **Criterios de aceptación:**
  - [x] Submenú facial: "Login" solo sin sesión; "Cerrar sesión" solo con sesión; "Enrolar" solo
        con permiso; selector de rol visible (antes el `OptionMenu` no se empaquetaba).
  - [x] Enrolamiento guarda una foto (`<id>.png`) del rostro; se ve en el panel de usuarios.
  - [x] Login guarda la primera foto reconocida (bajo `login_photo_threshold`) con fecha/hora.
  - [x] Admin: panel **Usuarios** (editar nombre/rol, re-enrolar, eliminar) y panel **Accesos**
        (tabla con fecha y foto de cada login).
  - [x] No-admin autenticado: solo "Mis accesos" (fecha, sin foto). Viewer/anónimo: nada.
  - [x] Gate verde.

## Plan
1. Dominio/puertos/adaptadores de fotos y accesos; runner guarda foto y evento.
2. GUI: submenú coherente + paneles de usuarios y accesos.
3. Tests, gate, review, docs, merge.

## Cambios (archivos)
- Dominio: `core/domain/access.py` (`AccessEvent`), `core/domain/face.py` (`EnrolledFace.preview`).
- Puertos: `core/ports/access_log.py` (`AccessLogRepository`), `core/ports/face_repository.py`
  (`update`/`delete`/`save_preview`/`preview_path`).
- Adaptadores: `adapters/image_codec.py`, `adapters/file_access_log_repository.py`,
  `adapters/file_face_repository.py` (preview + CRUD), `core/errors.py` (+`ImageEncodingError`,
  `AccessLogError`).
- Config: `face_auth.access_dir`, `face_auth.login_photo_threshold` (+validador ≤ `match_threshold`).
- Runner: `run_face_enroll(..., face_id=None)` re-enrola conservando nombre/rol/fecha; login
  registra `AccessEvent` con la primera foto de ESA identidad; `_RecognitionWorker.process(frame,
  observations)`.
- GUI: `cli/face_menu_gui.py` (OptionMenu empaquetado, botones por sesión), `cli/face_users_gui.py`,
  `cli/face_access_gui.py`, `cli/face_adapters.py`; `cli/menu_gui.py` (constantes de Treeview).
- Tests: `test_face_access_log.py`, `test_image_codec.py`, `test_face_users_gui.py`,
  `test_face_access_gui.py`, `test_face_enroll_runner.py` y ampliaciones de repo/dominio/menú.

## Decisiones
- Fotos en PNG (Tk no carga JPEG sin PIL) y en `<store>/<id>.png`; el JSON guarda el nombre.
- Accesos en `data/access/logins.jsonl` + `images/<timestamp>_<id>.png`.
- `login_photo_threshold` (0.35) más estricto que `match_threshold` (0.45): solo se guarda una
  foto cuando la coincidencia es clara; se asocia a la identidad que confirma (no a otra cara).
- Seguridad: el panel de accesos fuerza `find_by_face` + sin foto para no-admin; el panel de
  usuarios y el re-enrolamiento exigen admin; `image_path` del puerto valida el nombre (anti
  path-traversal).
- Rol preseleccionado al enrolar = `face_auth.default_role` si está permitido (antes quedaba
  "admin" por defecto para un admin).

## Tests y gate (resultados reales)
- `uv run lint`: OK. `uv run typecheck`: OK (199). `uv run test`: **1198 passed** (95.53%).
- `uv run check-arch`: 3/3.

## Revisión (hallazgos y correcciones)
- Reviewer: requiere cambios → aplicados: foto de login asociada a la identidad correcta (antes
  podía guardar la foto de otra cara), rol por defecto del selector, `require_role(ADMIN)` en
  re-enrolamiento, `image_path` en el puerto (anti path-traversal), id embebido vs nombre de
  archivo, validador `login_photo_threshold <= match_threshold`, `delete` quita el id del índice.

## Commits
- Pendiente `git-ops`.

## Pendientes / riesgos
- Verificar con cámara real: fotos de enrolamiento/login y paneles en el `.exe`.
- `data/access/` y `data/faces/` son datos de usuario (backup = copiar la carpeta).
