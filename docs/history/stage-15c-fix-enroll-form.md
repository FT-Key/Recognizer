# Fix 15c-2 — Formulario de enrolamiento coherente + "Ver detalle"

- **Rama:** stage/15c-fix-enroll-form
- **Estado:** completada
- **Objetivo:** ocultar los campos Nombre/Rol cuando el usuario no puede enrolar (aparecían
  aunque el botón Enrolar estuviera oculto) y renombrar el botón del panel de accesos a
  "Ver detalle".
- **Criterios de aceptación:**
  - [x] El formulario (Nombre + Rol + nota de primer rostro) se muestra solo si hay permiso
        de enrolar; si no, se oculta y aparece "sin permiso para enrolar".
  - [x] El selector de rol se recrea si cambian los roles permitidos (p. ej. tras login).
  - [x] Botón "Ver detalle" (antes "Ver imagen") en el panel de accesos.
  - [x] Gate verde.

## Causa
El formulario Nombre/Rol se creaba y empaquetaba siempre; solo el botón Enrolar se ocultaba
sin permiso, dejando campos sin utilidad visibles.

## Cambios (archivos)
- `cli/face_menu_gui.py`: `enroll_form` con `_sync_enroll_form` (muestra/oculta y recrea el
  `OptionMenu` según los roles permitidos); `refresh_session_ui` lo sincroniza.
- `cli/face_access_gui.py`: `ACCESS_VIEW_TEXT = "Ver detalle"` y textos asociados.
- `tests/unit/test_face_menu_gui.py`: `destroy` en los fakes y tests del formulario
  (oculto sin permiso, visible para admin).

## Tests y gate (resultados reales)
- `uv run lint`: OK. `uv run typecheck`: OK (199). `uv run test`: **1201 passed** (95.53%).
- `uv run check-arch`: 3/3.

## Commits
- Pendiente `git-ops`.
