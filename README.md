# Recognizer

Reconocimiento de rostro y gestos de manos mediante cámara para ejecutar acciones locales
(overlay, teclado/multimedia, comandos y puntero), con una arquitectura preparada para
roles/permisos y despliegue web futuro.

## Estado del proyecto

Etapa 7 (abrir enlaces) completada. Estado vivo en
[`docs/STATE.md`](docs/STATE.md) e historial en [`docs/history/index.md`](docs/history/index.md).

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
uv run recognizer                      # ventana con acciones y puntero (a activa/desactiva)
uv run recognizer --no-actions         # detección y overlay sin ejecutar acciones
uv run recognizer --no-pointer         # detección y acciones sin mover el cursor
uv run recognizer --no-window --frames 30  # comprobación sin ventana
```

La sección `actions` de `config.yaml` mapea gestos a teclas multimedia (`media_key`),
atajos (`hotkey`), comandos (`command`, argv sin shell) y scripts (`script`; ejemplos
comentados), además de abrir enlaces (`open_links`).

La sección `pointer` de `config.yaml` configura el puntero virtual: gesto de activación
(`activation_gesture`), `active_zone` (porción del fotograma que se proyecta a la pantalla),
suavizado (`smoothing`: `none`/`ema` con `alpha`) y `mirror_x` (vista espejo).

## Gestos personalizados

El vocabulario de gestos es abierto (`GestureId`): además de los 7 gestos predefinidos de
MediaPipe, se pueden declarar gestos propios y mapearles acciones. Dos fuentes:

- **Modelo custom:** entrena un bundle de MediaPipe (Model Maker) y apunta
  `gestures.model_path` a tu `.task`; declara sus etiquetas en `gestures.custom_labels`
  para que el pipeline las acepte.
- **Reglas de landmarks (sin entrenar):** define gestos geométricos en `gestures.rules`
  (dedos `extended`/`folded`, `direction` de un dedo y `angle` entre dos dedos). Se
  configura `rules_priority` (`rules_first`/`model_first`) y los umbrales en
  `rule_thresholds`.

```yaml
gestures:
  custom_labels: []
  rules_priority: rules_first
  rule_thresholds: {straight_angle_deg: 160.0, direction_tolerance_deg: 30.0}
  rules:
    L_Sign:
      extended: [thumb, index]
      folded: [middle, ring, pinky]
      angle: {a: thumb, b: index, min_deg: 50, max_deg: 110}
```

Cualquier gesto del catálogo (predefinido, custom o de regla) puede usarse como clave en
`actions.mappings` y en `pointer.activation_gesture`.

## Acciones script

Un gesto puede lanzar scripts locales en 4 formatos (`.py`, `.ps1`, `.bat`/`.cmd`, `.sh`),
resolviendo el intérprete por extensión (`interpreter: auto`) o forzándolo:

```yaml
actions:
  mappings:
    ILoveYou:
      type: script
      path: scripts/mi_script.py
      args: ["--modo", "rapido"]
      interpreter: auto        # auto|python|powershell|cmd|bash|direct
      working_dir: .
      blocking: false          # true espera al script (detiene la cámara)
      timeout_seconds: 0       # obligatorio > 0 si blocking: true
      pass_context: true       # variables RECOGNIZER_GESTURE/_HANDEDNESS/_CONFIDENCE/_TIMESTAMP
```

- **No bloqueante** (`blocking: false`, por defecto): lanza el script en segundo plano y
  el bucle de cámara sigue.
- **Bloqueante** (`blocking: true`): espera a que termine; exige `timeout_seconds > 0` para
  no congelar la app. Si el script expira se registra un `WARNING` y la app continúa.
- **Contexto**: con `pass_context: true` el script recibe el gesto en variables de entorno
  `RECOGNIZER_*`. Ejecución con `shell=False` (el `argv` proviene de `config.yaml`).

## Abrir enlaces (playlist)

La acción `open_links` abre enlaces en Chrome de forma **secuencial** (no aleatoria): cada
vez que se confirma el gesto se abre el siguiente de la lista y, al agotarla, vuelve al
principio. Si Chrome ya está abierto abre una pestaña nueva; si no, lo lanza y navega.

```yaml
actions:
  mappings:
    ILoveYou:
      type: open_links
      urls:
        - "https://www.youtube.com/watch?v=mlabBbn_fHI&t=0s"
        # añade más enlaces aquí (se abren en orden)
      browser: ""   # opcional: ruta a chrome.exe; vacío = autodetectar
```

Por defecto `ILoveYou` está mapeado a esta acción. El índice de la playlist vive en memoria
(se reinicia al arrancar la app). El adaptador actual solo integra Chrome.

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
| 1 | Manos: landmarks + overlay + EventBus | completada |
| 2 | Gestos predefinidos + estabilizador | completada |
| 3 | Acciones locales (teclado/multimedia, comandos) | completada |
| 4 | Puntero virtual | completada |
| 5 | Gestos personalizados (vocabulario abierto + reglas) | completada |
| 6 | Acciones script (bloqueante/no bloqueante) | completada |
| 7 | Abrir enlaces (playlist secuencial) | completada |
| 8 | Identidad/roles y plan web |
| 9 | Enrolamiento facial y despliegue web |

## Documentación

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — arquitectura, patrones y reglas
- [`docs/WORKFLOW.md`](docs/WORKFLOW.md) — flujo por etapas con subagentes
- [`docs/STATE.md`](docs/STATE.md) — estado actual del proyecto
- [`docs/WEB-PLAN.md`](docs/WEB-PLAN.md) — plan futuro de despliegue web
