# Etapa 15d — Clave de respaldo por usuario

- **Rama:** stage/15d-clave-respaldo
- **Estado:** completada (commits pendientes `git-ops`)
- **Objetivo:** que cada rostro enrolado tenga una clave (asignada en el enrolamiento, con
  confirmación) y pueda iniciar sesión con ella cuando la cámara no funcione o el
  reconocimiento facial falle.
- **Criterios de aceptación:**
  - [x] `EnrolledFace.password_hash` persistido; legado sin clave migra a `""`.
  - [x] Enrolamiento pide clave + confirmación (obligatoria en alta; en re-enrolar vacío = conservar).
  - [x] Login con clave (usuario/ID + clave) por consola y por GUI; sesión y acceso registrados.
  - [x] Panel de usuarios muestra si hay clave y permite asignar/cambiar la clave.
  - [x] Hash con PBKDF2-HMAC-SHA256 (sal aleatoria, comparación en tiempo constante).
  - [x] Gate verde (lint, typecheck, test >= 80%, check-arch).

## Plan
1. Dominio `core/domain/credentials.py` (hash/verify/validate/authenticate) + campo en `EnrolledFace`.
2. Repositorio: persistir `password_hash` y migración de legado.
3. Config `face_auth.min_password_length`; prompts en `core/constants.py`.
4. Runners: enrolamiento con clave; `run_face_login_password`.
5. GUI: formulario de enrolamiento con clave, diálogo de login por clave, submenú y panel de usuarios.
6. Tests + gate; revisión; documentación.

## Cambios (archivos)
- `core/domain/credentials.py` (nuevo): `hash_password`/`verify_password` con PBKDF2-HMAC-SHA256
  (sal aleatoria de 16 bytes, 600k iteraciones, `hmac.compare_digest`), `validate_password` y
  `authenticate` (por nombre/ID case-insensitive; hash dummy si el usuario no existe para no
  filtrar por tiempos).
- `core/domain/face.py`: `EnrolledFace.password_hash` (default `""` para migrar legado);
  `EnrollmentBuilder.build(..., password_hash=...)`.
- `adapters/file_face_repository.py`: persiste `password_hash`; JSON legado sin la clave → `""`.
- `core/config.py` + `config.yaml`: `face_auth.min_password_length` (default 4).
- `core/constants.py`: `PASSWORD_HASH_*`, `DEFAULT_MIN_PASSWORD_LENGTH` y prompts de enrolamiento/login.
- `cli/apps/face_auth.py`: enrolamiento pide clave + confirmación (obligatoria en alta; vacío al
  re-enrolar conserva la actual); `run_face_login_password` (login sin cámara, consola opción 3);
  escribe sesión y registra el acceso sin foto.
- `cli/face_password_gui.py` (nuevo): diálogo "Entrar con clave" del submenú facial.
- `cli/face_enroll_gui.py`, `cli/face_menu_gui.py`, `cli/face_users_gui.py`, `cli/menu_gui.py`:
  formulario con clave, botón de login por clave y columna "Clave" (si/-) con edición
  (vacío conserva; clave inválida aborta el guardado).
- `pyproject.toml`: per-file-ignore `S105` para etiquetas/prompts de la UI facial (falsos positivos).

## Decisiones
- PBKDF2-HMAC-SHA256 con sal de 16 bytes y 600k iteraciones (stdlib, sin dependencias).
- Mínimo de 4 caracteres configurable (`min_password_length`): credencial de respaldo local,
  no una política corporativa. Decisión consciente tras la revisión.
- La clave es opcional para el rostro, pero obligatoria al crear uno nuevo; al re-enrolar,
  dejarla vacía conserva la actual.
- Los rostros enrolados antes de esta etapa no tienen clave hasta que un admin la asigne.

## Tests y gate (resultados reales)
- `uv run lint` OK; `uv run typecheck` OK (mypy strict, 206 archivos).
- `uv run test` **1250 passed** (cobertura 95.57%).
- `uv run check-arch` 3/3.
- `uv run smoke --frames 30 --no-window` 17.0 FPS.

## Revisión (hallazgos y correcciones)
- Reviewer: apta. Se aplicaron los hallazgos menores: hash dummy anti-enumeración,
  `min_password_length` respetado en el panel de usuarios, abortar el guardado con clave
  inválida y subir las iteraciones a 600k.
- Queda como decisión consciente el mínimo de 4 caracteres (configurable).

## Commits
- Pendientes: `git-ops` (commits en la rama, merge `--no-ff` a `dev`, push).

## Pendientes / riesgos
- Verificación manual del usuario del diálogo de clave y del `.exe`.
- La clave es un respaldo local; el hash vive en `data/faces/<id>.json` (directorio 0o700).
