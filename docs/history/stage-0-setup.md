# Etapa 0 — Setup, gate estricto y configuración de opencode

- **Rama:** stage/0-setup
- **Estado:** completada
- **Objetivo:** dejar el proyecto ejecutable con calidad automatizada, arquitectura
  verificable, configuración de agentes y prueba real de cámara.
- **Criterios de aceptación:**
  1. Repo git con `main`/`dev`/`stage/0-setup` y remoto configurado.
  2. Python 3.12 con `uv` y dependencias instaladas.
  3. Gate completo en verde (ruff, mypy strict, pytest >= 80%, import-linter).
  4. Smoke de cámara real ejecutable sin ventana.
  5. opencode: agentes, skills, comandos y sistema STATE/history operativos.

## Plan
1. Entorno: uv + Python 3.12, repo git, remoto.
2. Estructura src/tests/scripts/config.
3. Core base: Frame, puerto FrameSource, configuración tipada, errores.
4. Adaptador OpenCVCamera y CLI smoke.
5. Gate estricto + contratos de arquitectura.
6. Documentación y configuración de opencode.

## Cambios (archivos)
- `pyproject.toml`: deps, entry points, ruff/mypy/pytest/coverage/import-linter.
- `config.yaml`: configuración de cámara (única fuente de valores ajustables).
- `src/recognizer/core/`: `domain/frame.py`, `ports/frame_source.py`, `config.py`,
  `constants.py`, `errors.py`.
- `src/recognizer/adapters/camera_opencv.py`: adaptador con `capture_factory` inyectable.
- `src/recognizer/settings.py`: carga YAML validada con pydantic.
- `src/recognizer/cli/smoke.py` y `src/recognizer/cli/quality.py`.
- `tests/unit/`: frame, config, settings y cámara (doble de VideoCapture).
- `scripts/download_models.py`; modelos descargados en `models/`.
- `AGENTS.md`, `opencode.json`, `.opencode/` (5 agentes, 2 skills, 4 comandos).
- `docs/`: STATE, ARCHITECTURE, WORKFLOW, WEB-PLAN e historial.

## Decisiones
- Python 3.12 aunque el sistema tenga 3.14: mediapipe/opencv no garantizan wheels en 3.14.
- `capture_factory` inyectable para tests sin hardware (puerto implícito del adaptador).
- Los comandos del gate se exponen como entry points (`uv run lint`, etc.) para que los
  agentes no dependan de la sintaxis del shell.
- El historial por etapa se separa del STATE para no gastar tokens leyendo de más.
- Revisión de la etapa: durante el bootstrap los subagentes recién creados aún no están
  cargados (opencode los lee al arrancar), así que la revisión se hizo manualmente contra
  el checklist de `AGENTS.md`; a partir de la etapa 1 aplica el `reviewer`.

## Tests y gate (resultados reales)
- `uv run lint`: ruff check y format OK.
- `uv run typecheck`: mypy 2.3.1 strict, sin errores (18 archivos).
- `uv run test`: 21 tests, 98.39% de cobertura (umbral 80%).
- `uv run check-arch`: 3 contratos KEPT (0 rotos).
- `uv run smoke --frames 30 --no-window`: 30 fotogramas, 29.3 FPS de media.

## Commits
- `391fa1e` `chore(repo): scaffold inicial del repositorio` (en `main`).
- `a3e6c05` `chore(setup): proyecto uv, dependencias y gate estricto`
- `7c814dc` `feat(core): camara, configuracion tipada, smoke y tests`
- `7c01998` `chore(opencode): agentes, skills y comandos del flujo por etapas`
- `6c64be9` `docs: arquitectura, workflow, estado e historial`
- `b613aeb` `merge: etapa 0 - setup, gate estricto y configuracion opencode` (en `dev`)

## Pendientes / riesgos
- Los subagentes quedan operativos tras reiniciar opencode (carga de configuración).
- `uv` debe abrirse desde una terminal nueva para estar en PATH.
- MediaPipe 1.0.1 es la nueva API de Tasks: la etapa 1 debe validar su superficie exacta.
