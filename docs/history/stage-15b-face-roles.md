# Etapa 15b — Roles y permisos sobre login facial

- **Rama:** stage/15b-face-roles
- **Estado:** completada
- **Objetivo:** el login 15a abre sesión con rol; el launcher solo muestra/permite apps según `PolicyEngine`; enrolar asigna rol (primer usuario = admin); base lista para DB distribuida.
- **Criterios de aceptación:**
  - [x] Roles `admin > operator > viewer`; sesión en `data/faces/session.json` con expiración.
  - [x] Menú filtra por rol; denegado avisa y no lanza.
  - [x] Solo admin (o/store vacío) puede enrolar rol admin; operator enrola viewer/operator.
  - [x] Migración: caras 15a sin rol → `operator` (o primer usuario → `admin` si store vacío).
  - [x] Gate verde: lint, typecheck, pytest ≥80%, check-arch 3/3.

## Plan
- Dominio `identity`: `Role`, `Identity`, `SessionRecord`, matriz `DEFAULT_PERMISSIONS` + `PolicyEngine` (fusión por clave con override `face_auth.permissions`).
- Puertos: `IdentityProvider` (`current_identity`/`require_role`/`refresh`) como seam para futura `DbIdentityProvider`.
- Adaptadores: `FileIdentityProvider` (sesión JSON con expiración) + `AllowAllIdentityProvider` (modo abierto Null Object); `file_face_repository` con rol + migración.
- `face.py`: campo `role` en `EnrolledFace` con default `OPERATOR` (compatibilidad 15a).
- `face_auth`: enroll con asignación de rol, login escribe sesión, logout la borra.
- Menú (`menu.py`/`menu_gui.py`): gating por rol + revalidación al clic.
- Config: `FaceAuthConfig` (`require_login`, `session_timeout_seconds`, `default_role`, `permissions`).

## Cambios (archivos)
- `src/recognizer/core/domain/identity.py` (nuevo): roles, sesión, `PolicyEngine`, identidad invitada viewer.
- `src/recognizer/core/ports/identity_provider.py` (nuevo): puerto de identidad/sesión.
- `src/recognizer/adapters/file_identity_provider.py` (nuevo): sesión en `session.json` + provider abierto.
- `src/recognizer/core/domain/face.py`: `EnrolledFace.role` (default `OPERATOR`), `build(..., role=...)`.
- `src/recognizer/adapters/file_face_repository.py`: persiste rol + migración legado→operator (primer usuario→admin si store vacío).
- `src/recognizer/cli/apps/face_auth.py`: enroll/login/logout con roles y sesión.
- `src/recognizer/cli/menu.py`, `src/recognizer/cli/menu_gui.py`: filtrado por rol + revalidación al lanzar.
- `src/recognizer/core/config.py`, `config.yaml`: `FaceAuthConfig` (`require_login`, `session_timeout_seconds`, `default_role`, `permissions`).
- `src/recognizer/core/errors.py`: `AuthError`; `src/recognizer/core/constants.py`: consts de sesión/roles.
- Tests: `tests/unit/test_identity_domain.py`, `test_identity_provider.py`, `test_identity_repository.py`, `test_identity_enroll.py`, `test_identity_menu.py`.

## Decisiones
- Matriz viewer/operator/admin por app en `DEFAULT_PERMISSIONS`; override de config se fusiona por clave de app.
- `require_login: false` por defecto (modo abierto con `AllowAllPolicy`); invitado = viewer.
- Migración fail-closed: legado sin rol → `operator`, rol inválido → `viewer`; primer usuario del store vacío → `admin`.
- Revalidación de permiso en el GUI al clic (no solo al listar; evita TOCTOU).
- Sesión en `session.json` junto al store, con expiración (`session_timeout_seconds`, `0` = sin expiración).

## Tests y gate (resultados reales)
- `uv run lint`: OK (ruff + format, 202 archivos).
- `uv run typecheck`: mypy strict sin errores en 177 archivos.
- `uv run test`: **1099 passed**, 2 deselected, cobertura 94.65% (≥80%).
- `uv run check-arch`: 3/3 contratos OK (141 archivos, 671 dependencias).

## Revisión (hallazgos y correcciones)
- Reviewer: apta para merge tras corregir TOCTOU en GUI (revalidar permiso al clic, no solo al filtrar), fallback fail-closed a viewer ante rol desconocido, y `mkstemp` envuelto para escritura atómica de sesión.

## Commits
- Pendientes de `git-ops` (rama `stage/15b-face-roles` sin merge a `dev`).

## Pendientes / riesgos
- Calibrar `face_auth.match_threshold` y `session_timeout_seconds` con cámara real.
- Decidir activación de `require_login: true` en despliegues que lo necesiten.
- Verificar `.exe` con el bundle facial+roles; etapa 15c (DB distribuida) implementa `DbIdentityProvider` sobre el mismo puerto.
