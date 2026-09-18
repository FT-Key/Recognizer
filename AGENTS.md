# AGENTS.md — Recognizer

Proyecto de visión por computadora en Python: reconoce rostro y gestos de manos con la
cámara para ejecutar acciones locales (overlay, teclado/multimedia, comandos, puntero) y,
a futuro, desplegarse en web con roles y permisos.

## Arranque de sesión (obligatorio)
1. `docs/STATE.md` se carga como instrucción: ahí está la fase actual, la rama y lo siguiente.
2. NO leas `docs/history/*` completo. Consulta `docs/history/index.md` y abre solo el
   archivo de etapa que necesites (manejo de tokens).
3. Flujo por etapas con subagentes: `docs/WORKFLOW.md`. Arquitectura: `docs/ARCHITECTURE.md`.

## Reglas no negociables
- Contrato de capas: `src/recognizer/core/**` no importa `adapters`, `cli`, `settings`
  ni librerías de infraestructura (`cv2`, `mediapipe`, `pynput`, `yaml`, `fastapi`).
  Verificación: `uv run check-arch`.
- Cero `typing.Any` en código propio. Cero strings/números mágicos: usa enums y
  `core/constants.py`; los umbrales y mapeos van en `config.yaml`.
- Efectos secundarios solo en `adapters/` y `cli/` (functional core, imperative shell).
- Patrones: aplica la regla de admisión de `docs/ARCHITECTURE.md`. Si no cumple, no se usa.
  Prohibidos por defecto: Singleton, AbstractFactory, broker externo de eventos,
  Repository para config, herencia mayor a un nivel.
- Eventos del dominio: dataclasses `frozen=True`; despacho con `match/case`.
- Sin `print` (usa `logging`), sin `except` desnudos; errores del dominio en `core/errors.py`.
- Todo cambio de comportamiento lleva tests. Los tests no usan hardware real
  (márcalos `@pytest.mark.integration`).
- Launcher multi-app: cada app importa sus dependencias de forma perezosa (solo al
  seleccionarse) y usa una sola vía de inferencia. Prohibido el doble procesamiento del
  mismo fotograma (p. ej. MediaPipe + YOLO a la vez) y cargar modelos de apps no elegidas.
  Toda app termina con `ESC`/`q` y vuelve al menú. Detalle: `docs/ARCHITECTURE.md` y skill
  `new-app`.

## Gate de calidad (obligatorio antes de cerrar una etapa)
- `uv run lint` — ruff check + format
- `uv run typecheck` — mypy --strict
- `uv run test` — pytest con cobertura >= 80%
- `uv run check-arch` — import-linter
- `uv run smoke --frames 30 --no-window` — cámara real

## Git
- Trabaja siempre en `stage/<n>-<slug>` (creada desde `dev`).
- Cierre: commits en la rama, `git checkout dev`, `git merge --no-ff`, `git push origin dev`.
- `main` es intocable desde el flujo local: solo el usuario mergea dev -> main en GitHub.

## Entorno
- Windows, Python 3.12 vía `uv` (no usar el Python 3.14 del sistema), GPU AMD sin CUDA
  (inferencia en CPU).
- Nunca `pip` directo: `uv add`. Modelos: `uv run python scripts/download_models.py`.
- Subagentes disponibles: `vision-dev`, `test-writer`, `reviewer`, `git-ops`, `docs-writer`.
  Llámalos solo cuando su especialidad sea necesaria.

## Autonomía
- No pidas permisos ni confirmaciones: elige la opción más razonable y registra la
  decisión (history de la etapa o `docs/STATE.md`).
- No uses la herramienta `question` salvo bloqueo real que impida avanzar.
- Reporta siempre breve: archivos tocados, resultado del gate, pendientes.
