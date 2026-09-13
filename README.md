# Recognizer

Reconocimiento de rostro y gestos de manos mediante cámara para ejecutar acciones locales
(overlay, teclado/multimedia, comandos y puntero), con una arquitectura preparada para
roles/permisos y despliegue web futuro.

## Estado del proyecto

Etapa 0 (setup) completada. Estado vivo en [`docs/STATE.md`](docs/STATE.md) e historial en
[`docs/history/index.md`](docs/history/index.md).

## Requisitos

- Windows 10/11 (desarrollo actual), Python 3.12 gestionado con `uv`
- Cámara web
- GPU AMD sin CUDA: la inferencia corre en CPU

## Inicio rápido

```powershell
uv sync
uv run python scripts/download_models.py
uv run smoke --frames 30 --no-window   # mide FPS y sale
uv run smoke                           # ventana en vivo (ESC o q para salir)
uv run recognizer                      # ventana en vivo con acciones (a activa/desactiva)
uv run recognizer --no-actions         # detección y overlay sin ejecutar acciones
uv run recognizer --no-window --frames 30  # comprobación sin ventana
```

La sección `actions` de `config.yaml` mapea gestos a teclas multimedia (`media_key`),
atajos (`hotkey`) y comandos (`command`, argv sin shell; el ejemplo va comentado).

## Gate de calidad

```powershell
uv run lint          # ruff check + format
uv run typecheck     # mypy --strict
uv run test          # pytest + cobertura >= 80%
uv run check-arch    # contratos de arquitectura (import-linter)
```

## Estructura

```
src/recognizer/core/      dominio, puertos y pipeline (sin infraestructura)
src/recognizer/adapters/  OpenCV, MediaPipe, acciones locales, persistencia
src/recognizer/cli/       comandos (smoke, gate de calidad)
config.yaml               configuración (única fuente de umbrales y mapeos)
scripts/                  utilidades (descarga de modelos)
tests/                    tests unitarios e integración (marcados)
docs/                     arquitectura, workflow, estado e historial
.opencode/                agentes, skills y comandos del flujo de trabajo
```

## Roadmap

| Etapa | Contenido |
|---|---|
| 0 | Setup, gate estricto y configuración | completada |
| 1 | Manos: landmarks + overlay + EventBus |
| 2 | Gestos predefinidos + estabilizador |
| 3 | Acciones locales (teclado/multimedia, comandos) |
| 4 | Puntero virtual |
| 5 | Identidad/roles y plan web |
| 6 | Enrolamiento facial y despliegue web |

## Documentación

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — arquitectura, patrones y reglas
- [`docs/WORKFLOW.md`](docs/WORKFLOW.md) — flujo por etapas con subagentes
- [`docs/STATE.md`](docs/STATE.md) — estado actual del proyecto
- [`docs/WEB-PLAN.md`](docs/WEB-PLAN.md) — plan futuro de despliegue web
