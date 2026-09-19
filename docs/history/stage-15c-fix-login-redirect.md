# Fix 15c — Redirección tras login + visor de imagen de accesos

- **Rama:** stage/15c-fix-login-redirect
- **Estado:** completada
- **Objetivo:** tras reconocer el rostro, mostrar cuenta regresiva y volver solo al menú; y
  reemplazar la foto inline del panel de accesos (se veía como una línea fina) por un botón
  "Ver imagen" que abre una ventana modal con la foto y los datos.
- **Criterios de aceptación:**
  - [x] Login: "Bienvenido <nombre> <ID> - Redirigiendo en 3.. 2.. 1.." y vuelve al submenú sin ESC.
  - [x] Panel de accesos: botón "Ver imagen" abre un `Toplevel` modal (`grab_set`) con foto, datos y Volver.
  - [x] Gate verde.

## Causa raíz
- El login solo terminaba con ESC/q; no había forma de que el bucle saliera solo.
- La foto inline usaba un `Label` con `width`/`height` en unidades de texto sobre `bg` del tema,
  que colapsaba a una franja de pocos píxeles.

## Cambios (archivos)
- `cli/runtime.py`: `RuntimeCallbacks.should_stop` (el bucle corta cuando devuelve `True`).
- `cli/apps/face_auth.py`: `_LoginState.greeted_at`/`done`; `_on_context` calcula la cuenta
  regresiva y `run_camera_loop(..., should_stop=lambda: state.done)`.
- `core/constants.py` + `core/config.py` + `config.yaml`: `face_auth.login_redirect_seconds` (3; 0 = sin redirección).
- `cli/face_access_gui.py`: botón "Ver imagen" (solo admin) + `_open_photo_window` modal con
  `grab_set`/`wait_window`; se elimina la foto inline.
- `tests/unit/test_face_access_gui.py`: fakes con `grab_set`/`Toplevel` y tests del modal.

## Decisiones
- Cuenta regresiva de 3 s configurable; el texto lo dibuja el bucle principal (fluido) aunque
  la inferencia sea lenta.
- Modal con `grab_set` para bloquear la lista; la foto se mantiene viva mientras el modal existe.

## Tests y gate (resultados reales)
- `uv run lint`: OK. `uv run typecheck`: OK (199). `uv run test`: **1199 passed** (95.53%).
- `uv run check-arch`: 3/3.

## Commits
- `fcb4a6f` feat(face-auth): cuenta regresiva de login y callback should_stop en el bucle.
- `b0bf695` feat(face-access): visor modal de foto en el panel de accesos.
- `3f5d693` test(face-access): cubrir visor modal de foto y fakes Toplevel/grab_set.

## Pendientes / riesgos
- Verificar con cámara real la cuenta regresiva y el visor modal.
