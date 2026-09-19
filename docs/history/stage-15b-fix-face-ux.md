# Fix 15b — Submenú facial gráfico + selector de cámara + guía de distancia honesta

- **Rama:** stage/15b-fix-face-ux
- **Estado:** completada
- **Objetivo:** el submenú facial deja la consola y se vuelve ventana vintage como el menú principal; el menú principal permite elegir cámara; el "acércate" imposible se explica y se calibra (umbral menor + marco objetivo real).
- **Criterios de aceptación:**
  - [x] FACE_AUTH en GUI abre submenú gráfico vintage (Enrolar/Login/Cerrar sesión/Volver, nombre + rol); consola sigue como fallback.
  - [x] Header del menú con selector de cámara (Detectar + ciclo) que propaga `device` a los runners.
  - [x] Overlay dibuja marco objetivo proporcional a `min_face_width_ratio` (no decorativo); default 0.18 + docs de calibración.
  - [x] Gate verde: lint, typecheck, pytest ≥80%, check-arch 3/3.

## Plan
- Submenú facial como `Toplevel` vintage (Enrolar/Login/Cerrar sesión/Volver, muestra nombre + rol).
- Selector de cámara en el header con puerto `CameraEnumerator`: Detectar + ciclo, propaga `device` a los runners.
- Marco objetivo en el overlay ligado al umbral `min_face_width_ratio` (guía de distancia honesta).

## Cambios (archivos)
- Nuevo `cli/face_menu_gui.py`: submenú facial gráfico vintage.
- `menu_gui.py`: selector de cámara en header + `EVENT_KEY_Q` para cerrar submenú.
- Nuevo `domain/camera.py`: lógica de selección de cámara.
- Nuevo `ports/camera_discovery.py` + `adapters/camera_discovery.py`: enumeración de cámaras.
- `adapters/overlay_face.py`: marco objetivo con `target_width_ratio`; `cli/apps/face_auth.py` pasa `min_width`.
- `core/constants.py`: default `0.18` + `MAX`; `config.yaml`: umbral y docs de calibración.
- Tests: `test_face_menu_gui.py`, `test_camera_discovery.py`, `test_face_overlay.py`.

## Decisiones
- Marco decorativo pasa a objetivo ligado al umbral `min_face_width_ratio`.
- Default `0.18` ≈ 230px a 1280 de ancho.
- `cv2` solo dentro de `list_cameras` (núcleo sin infraestructura).
- `device` se propaga vía `replace(request)`.
- Lector en cola muestra `[nombre, rol]`.
- Refresh de permisos al clic + `q` para cerrar el submenú.
- Consola como fallback si no hay GUI.

## Tests y gate (resultados reales)
- `uv run lint`: OK.
- `uv run typecheck`: mypy strict 183 archivos, OK.
- `uv run test`: pytest **1119 passed**, cobertura 94.59%.
- `uv run check-arch`: 3/3 contratos OK.

## Revisión (hallazgos y correcciones)
- Reviewer: apta para merge tras aplicar refresh de permisos al clic + tecla `q` para cerrar el submenú.

## Commits
- Cambios sin commitear en `stage/15b-fix-face-ux` (merge y commits pendientes de `git-ops`).

## Pendientes / riesgos
- Calibrar con cámara real `face_auth.min_face_width_ratio` y `match_threshold`.
- Probar selector con 2 cámaras físicas.
