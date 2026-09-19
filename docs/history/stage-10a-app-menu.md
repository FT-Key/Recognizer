# Etapa 10a — Launcher multi-app (menú) y roadmap de apps

- **Rama:** stage/10a-app-menu
- **Estado:** completada
- **Objetivo:** convertir `recognizer` en un launcher: sin argumentos abre un menú con la
  app de gestos habilitada y el resto visibles pero deshabilitadas, con salida de cada app
  de vuelta al menú, y dejar sentado el plan por etapas del resto de apps.
- **Criterios de aceptación:**
  - [x] `uv run recognizer` sin args muestra el menú con las 7 apps en el orden pedido.
  - [x] Las apps no implementadas se ven `[proximamente]` y no se pueden lanzar.
  - [x] `apps.enabled` permite deshabilitar una app implementada.
  - [x] Salir de una app (`ESC`/`q`) vuelve al menú, no cierra el programa.
  - [x] `recognizer` con flags sigue ejecutando la app de gestos (compatibilidad).
  - [x] Abrir el menú no carga MediaPipe/OpenCV ni abre la cámara.
  - [x] Gate verde: lint, mypy strict, pytest >= 80%, check-arch 3/3.

## Plan

1. Dominio: `AppId`, `AppInfo`, `AppAvailability`, `AppCatalog`, `AppRunRequest` y el
   `DEFAULT_APPS` ordenado.
2. Config: `AppsConfig` (`apps.enabled`) + sección en `config.yaml`.
3. CLI: `cli/paths.py` (rutas livianas), `configure_logging` en `console.py`,
   `cli/menu.py` (render + bucle + registro perezoso de runners) y `cli/app.py`
   (`run_gestures` + `main` con menú).
4. Tests: catálogo, config de apps y menú (incluida la vuelta al menú).
5. Docs/skills: `ARCHITECTURE`, `WORKFLOW`, skill `new-app`, agente `vision-dev`,
   `AGENTS.md`, `PENDING-TESTS` y este history.
6. Roadmap por etapas (abajo).

## Cambios (archivos)

- `src/recognizer/core/domain/app.py` (nuevo): catalogo de apps del launcher.
- `src/recognizer/core/config.py`: `AppsConfig` y `AppConfig.apps`.
- `src/recognizer/cli/paths.py` (nuevo): rutas y modo `frozen` sin dependencias de visión.
- `src/recognizer/cli/console.py`: `configure_logging` reutilizable.
- `src/recognizer/cli/menu.py` (nuevo): render, bucle interactivo y `resolve_runner`.
- `src/recognizer/cli/app.py`: `run_gestures(request, ...)`, `main` con menú y
  `--list-apps`; helpers de rutas movidos a `cli/paths.py`.
- `config.yaml`: sección `apps.enabled`.
- `packaging/recognizer.spec`: `hiddenimports` de `recognizer.cli.menu`.
- `tests/unit/test_app_domain.py`, `test_menu.py`, `test_apps_config.py` (nuevos).
- `docs/ARCHITECTURE.md`, `docs/WORKFLOW.md`, `docs/PENDING-TESTS.md`,
  `docs/history/index.md`, `docs/STATE.md`, `AGENTS.md`,
  `.opencode/skills/new-app/SKILL.md`, `.opencode/agents/vision-dev.md`.

## Decisiones

- **El menú no es una app**: `AppCatalog` es dominio puro; los runners son shell (`cli`).
  No se crea un puerto `AppRunner` en `core` porque no aísla una dependencia externa y los
  runners son orquestación con efectos (regla de admisión de patrones).
- **Disponibilidad = implementada + habilitada**: `implemented` vive en código (no se puede
  "habilitar" lo que no existe); `apps.enabled` es un override de configuración.
- **Vuelta al menú sin cambios en el runtime**: `run_camera_loop` ya termina con `ESC`/`q`;
  el runner retorna y el bucle del menú se repite. No hizo falta un canal de "quit".
- **Carga perezosa**: `cli/paths.py` y `console.py` no importan `cv2`/`mediapipe`, así que
  el menú arranca sin cargar visión. Los runners se importan dentro de `resolve_runner`.
- **Numeración**: la etapa 10 se redefine como "launcher + contador de personas" en fases
  `10a` (este launcher), `10b`/`10c` (contador). El despliegue web ya estaba hecho en la
  etapa 9; el reconocimiento facial pasa a la etapa 15 (app independiente).

## Tests y gate (resultados reales)

- `uv run lint`: ruff check + format OK (126 archivos).
- `uv run typecheck`: mypy strict OK (126 archivos).
- `uv run test`: 635 tests, cobertura 96.05% (umbral 80%).
- `uv run check-arch`: 3/3 contratos KEPT.
- `uv run recognizer --list-apps`: menú correcto (7 apps en orden, gestos `[disponible]`).
- `uv run smoke`: pendiente de ejecución manual del usuario (checklist en
  `docs/PENDING-TESTS.md`).

## Roadmap de apps (plan por etapas)

Orden: primero las que **no** requieren entrenamiento, luego las que sí.

| Etapa | App | Entrenamiento | Fases sugeridas |
|---|---|---|---|
| 10b | Contador de personas | No (`yolo26n.pt`) | detección + conteo |
| 10c | Contador de personas | No | tracking (`model.track`), zona/línea, overlay |
| 11 | Anti-intrusos | No | ROI + debounce + alerta (`CommandRunner`/`ScriptRunner`) |
| 12 | Postura ergonómica | No (`yolo26n-pose.pt`) | keypoints + reglas de ángulo en `core` |
| 13 | Detector EPP de obra | Sí | dataset público `construction-ppe` o `best.pt` propio |
| 14 | Inventario por cámara | Sí | dataset propio + persistencia (`Repository`) |
| 15 | Reconocimiento facial | Enrolamiento | `enroll`/`login`, embeddings y roles/permisos |

Notas de arquitectura para el roadmap:
- Puerto nuevo previsto: `ObjectDetector` (`detect(frame) -> Detections`) en `core/ports`,
  adaptador `UltralyticsDetector` en `adapters/`; añadir `ultralytics`/`torch` a
  `forbidden_modules` del core en `pyproject.toml`.
- Face auth: puerto `FaceEncoder` + `FileFaceRepository` (eje de persistencia), demo
  `login` que saluda `Bienvenido <nombre>`.
- Cada app: ver checklist de `docs/WORKFLOW.md` y skill `new-app`.

## Revisión (hallazgos y correcciones)

- Pendiente de `/stage-review` antes del merge (el usuario decidirá si lo ejecuta).

## Commits

- Pendiente: los crea `git-ops` al cerrar la etapa.

## Pendientes / riesgos

- Verificación manual del menú y del `.exe` (checklist en `docs/PENDING-TESTS.md`).
- `ultralytics`/`torch` añaden ~300 MB al `.exe`; revisar `packaging/recognizer.spec` al
  implementar la etapa 10b.
- La rama `stage/9c-scroll` sigue sin mergear a `dev`; el launcher se apila sobre ella.
