# Etapa 15d-login-dni-ux — Login por ID/DNI y formularios con mensajes

- **Rama:** stage/15d-login-dni-ux
- **Estado:** completada
- **Objetivo:** (1) Enter envía el login con clave; (2) el fallo muestra el error
  en el diálogo con reintento en lugar de volver al menú; (3) el login acepta
  ID o DNI (ya no nombre: hay homónimos) con DNI nuevo campo enrolable y
  editable; (4) formularios validados con mensajes visibles al usuario.
- **Criterios de aceptación:**
  - [ ] Enter en el diálogo de clave equivale a Ingresar.
  - [ ] Clave errónea: mensaje rojo en el diálogo y reintento sin cerrarlo.
  - [ ] `EnrolledFace.national_id` persistido (legado `""`); DNI 7-8 dígitos, único.
  - [ ] Enrolamiento pide DNI (obligatorio en alta; vacío al re-enrolar conserva).
  - [ ] Login por ID (`F-0001`) o DNI; el nombre ya no autentica.
  - [ ] CRUD muestra y edita el DNI con validación visible.
  - [ ] Enrolamiento y edición muestran errores de validación en rojo en la UI.
  - [ ] Gate verde.

## Plan
1. Dominio: `normalize/validate_national_id` en `face.py`, campo y builder; `authenticate` por ID/DNI.
2. Repositorio: persistir `national_id` + migración.
3. Runner: DNI en enrolamiento (único), login ID/DNI, fallo con identidad por ID/DNI.
4. GUI: Enter + error con reintento en login; DNI y errores visibles en enrolamiento y CRUD.
5. Tests + gate; documentación; merge.

## Cambios (archivos)
- `core/domain/face.py`: `normalize/validate_national_id`, `EnrolledFace.national_id`, `build(..., national_id=...)`.
- `core/domain/credentials.py`: `authenticate(..., user=...)` solo por ID (`F-0001`) o DNI normalizado; el nombre ya no autentica; dummy anti-enumeración conservado.
- `core/constants.py`: `NATIONAL_ID_MIN/MAX_DIGITS`, `FACE_ENROLL_NATIONAL_ID_PROMPT`, `FACE_LOGIN_USER_PROMPT` → "Usuario (ID o DNI)".
- `adapters/file_face_repository.py`: clave `national_id` + migración a `""`.
- `cli/apps/face_auth.py`: `_request/_resolve_enroll_national_id` (obligatorio y único en alta, vacío conserva al re-enrolar excluyéndose); login ID/DNI; fallo con identidad por ID/DNI; docstring del submenú corregido.
- `cli/face_adapters.py`: `national_id_taken` (tolerante, solo proveedor de archivos).
- `cli/face_enroll_gui.py`: campo DNI + etiqueta de error roja; validaciones visibles (nombre, DNI único, clave); lector con prompt de DNI.
- `cli/face_password_gui.py`: Enter global, error rojo con reintento sin cerrar ni ocultar, etiqueta "ID o DNI".
- `cli/face_users_gui.py`: columna DNI, edición con validación visible (formato, unicidad, clave), DNI en el detalle.
- Tests: credenciales (ID/DNI, nombre ya no entra, homónimos), runner (DNI requerido/duplicado/inválido, re-enrolar), formularios (errores visibles, Enter, reintento), dominio, repositorio, CRUD.

## Decisiones
- El nombre deja de autenticar: con homónimos es ambiguo. Solo ID o DNI.
- DNI requerido en alta (7-8 dígitos, único); al re-enrolar, vacío conserva; legado `""`.
- El error de login fallido se muestra en el diálogo sin cerrarlo; la consola sigue por log.
- En el log no se registra el valor del DNI duplicado (dato personal).

## Tests y gate (resultados reales)
- `uv run lint` OK; `uv run typecheck` OK (mypy strict, 206 archivos).
- `uv run test` **1281 passed** (cobertura 95.63%).
- `uv run check-arch` 3/3.
- `uv run smoke --frames 30 --no-window` OK.

## Revisión (hallazgos y correcciones)
- Reviewer: apta. Aplicados: código muerto tras `return` en `face_enroll_gui` y log sin valor del DNI duplicado.

## Commits
- `feat(login)`: DNI + login por ID/DNI + formularios con errores visibles (esta rama, merge `--no-ff` a `dev`, push).

## Pendientes / riesgos
- Verificación manual: diálogo de clave (Enter, error, reintento) y enrolamiento con DNI.
