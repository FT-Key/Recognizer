# Fix 15b-6 — Doble apertura de cámara en la app facial

- **Rama:** stage/15b-fix6-face-double-open
- **Estado:** completada
- **Objetivo:** el login/enrolamiento facial fallaba con `CameraError: La camara ya esta
  abierta` (parpadeo y vuelta al submenú) tras introducir la captura asíncrona.
- **Criterios de aceptación:**
  - [x] La app facial abre la cámara una sola vez y muestra el video.
  - [x] Gate verde.

## Causa raíz
Con `LatestFrameSource`, el runner entraba la cámara al `ExitStack` (`OpenCVCamera.__enter__`
→ `open()`) y luego `LatestFrameSource.open()` volvía a llamar `source.open()` sobre la misma
cámara ya abierta → `CameraError`. La segunda llamada a `open()` es la que aparecía en el log
justo tras "OK Abriendo camara".

## Cambios (archivos)
- `cli/apps/face_auth.py`: la cámara se crea sin entrar al stack; `LatestFrameSource` la abre y
  la libera (enrolamiento y login). Se elimina la doble apertura.

## Tests y gate (resultados reales)
- `uv run lint`: OK. `uv run typecheck`: OK (186). `uv run test`: **1130 passed** (94.69%).
- `uv run check-arch`: 3/3.

## Commits
- Pendiente `git-ops`.

## Pendientes / riesgos
- Verificar con cámara real que login/enrolamiento muestran video y que ESC/q vuelve al menú.
