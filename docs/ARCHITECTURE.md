# Arquitectura

## Visión general

Hexagonal (puertos y adaptadores) + pipeline de frames + EventBus tipado in-process.
El núcleo (`core`) no conoce frameworks ni sistema operativo; los adaptadores implementan
los puertos; `bootstrap`/CLI son el composition root (inyección por constructor).

```
frame -> [HandPipeline] -> GestureStabilizer -> EventBus -> ActionSink (decoradores)
```

## Capas y contrato de dependencias

- `core/domain`: vocabulario (enums), objetos de valor (`Frame`), eventos frozen, acciones.
- `core/ports`: Protocols que el núcleo necesita (`FrameSource`, `HandTracker`, `EventBus`...).
- `core/pipeline`: processors + `PipelineBuilder` (pipes & filters).
- `adapters/`: OpenCV, MediaPipe, pynput, subprocess, persistencia, red (futuro).
- `settings.py`, `bootstrap.py`, `cli/`: composición y entrada.
- Contratos verificados por import-linter en `pyproject.toml`: el core no importa capas
  externas ni infraestructura; los adapters no importan cli/settings.

## Ejes de cambio previstos (justifican las abstracciones)

1. Fuente de frames: cámara local -> stream web.
2. Destino de acciones: local (SO) -> red/remoto.
3. Identidad: sin enrolamiento -> rol/perfil con permisos.
4. Persistencia: ninguna -> embeddings de rostro / dataset de gestos.
5. Interfaz: overlay OpenCV -> UI de escritorio -> web.

## Patrones y regla de admisión

| Patrón | Uso real en el proyecto | Eje |
|---|---|---|
| Strategy | `GestureClassifier`, `PointerSmoothing`, `PolicyEngine` | 1,2,3 |
| Factory | `PipelineFactory` / `ActionFactory` desde config | 1,2 |
| Adapter | Puertos hacia MediaPipe/OpenCV/pynput/subprocess/red | 1,2 |
| Repository | Embeddings/dataset (solo cuando existan) | 4 |
| DI | Inyección por constructor + composition root | todos |
| Observer | `EventBus` tipado in-process | 1,2,5 |
| Decorator | `Gated(Debounced(Logged(action)))`, `ConfidenceFilter` | 2,3 |
| Facade | `RecognizerApp`, `MediaPipeTasksFacade` | todos |
| Builder | `PipelineBuilder` (uno solo) | 1 |
| Command | `Action` con parámetros y `execute(ctx)` | 2 |
| Null Object | `AllowAllIdentity`, `NoOpAction` (MVP sin roles) | 3 |

**Regla de admisión:** un patrón entra solo si (a) hay 2+ implementaciones reales o
previstas en el roadmap, (b) aísla una dependencia externa, o (c) los tests necesitan un
doble. Si no cumple: código directo, sin interfaz.
**Prohibidos por defecto:** Singleton, AbstractFactory, broker externo de eventos,
Repository para config, herencia mayor a un nivel, capas sin eje de cambio.

## Prácticas obligatorias

- Enums y constantes centrales (`core/constants.py`, `core/domain`); nada de strings o
  números mágicos en el código que los usa; umbrales y mapeos en `config.yaml`.
- Cero `typing.Any` en código propio (`mypy --strict` + ANN401). Fronteras con librerías
  externas vía `Protocol` + `cast` documentado.
- Dataclasses `frozen=True` para eventos y objetos de valor; `match/case` para despacho;
  argumentos keyword-only en APIs con más de un parámetro.
- Errores del dominio en `core/errors.py`; sin `except` desnudos; recursos con context managers.
- Functional core / imperative shell: la lógica no tiene efectos; los efectos viven en
  `adapters/`.

## Gestos personalizados (etapa 5)

El vocabulario de gestos es abierto: `GestureId` (value object) sustituye al enum cerrado
`GestureName`; `GestureCatalog` valida contra la config las etiquetas predefinidas,
custom (`gestures.custom_labels`) y de reglas. Las reglas geométricas de landmarks viven
en `core/pipeline/landmark_rules.py` (core puro, sin infraestructura) y
`LandmarkRuleProcessor` resuelve reglas vs. modelo según `rules_priority`. Un modelo
custom (Model Maker) solo requiere cambiar `gestures.model_path` y declarar
`custom_labels`; el adaptador filtra las etiquetas por el catálogo.

## Acciones locales y scripts (etapa 6)

Las acciones locales son `media_key`, `hotkey`, `command` y `script`. Los scripts se
ejecutan a través del puerto `ScriptRunner` (`core`) implementado por
`SubprocessScriptRunner` (`adapters`), que resuelve el intérprete por extensión
(`.py/.ps1/.bat/.cmd/.sh`) y soporta modo bloqueante (con `timeout_seconds > 0`) y no
bloqueante (`shell=False`, `argv` desde config). El contexto del gesto se pasa de forma
opt-in por variables de entorno `RECOGNIZER_*`.

La acción `open_links` abre URLs en el navegador a través del puerto `LinkOpener`
(implementado por `ChromeLinkOpener`), recorriendo una lista de forma secuencial; el
adaptador autodetecta Chrome y lanza `chrome.exe <url>` (pestaña nueva o arranque del
navegador según su estado).

## Gestos compuestos y menús (etapa 8)

Con dos manos, una sostiene un gesto modificador y la otra elige una opción de un menú
(`actions.menus`). La resolución vive en `core/actions/menus.py` (domain puro:
`HandGestureTracker`, `find_menu_match`) y la aplica `GestureActionDispatcher`, que
consume el gesto disparador (`consume_trigger`) y evita repeticiones hasta liberar la mano.
El puntero se desactiva con más de una mano visible (`PointerDetectionProcessor`). La
lateralidad del modelo se puede corregir con `gestures.swap_handedness`.

## Gate

`uv run lint` · `uv run typecheck` · `uv run test` (cobertura >= 80%) ·
`uv run check-arch` · `uv run smoke --frames 30 --no-window`.

## Arquitectura dual: Web + Desktop

Recognizer tiene **dos aplicaciones** que comparten el mismo core conceptual
(reconocimiento de gestos) pero son implementaciones independientes:

### Desktop (`src/recognizer/`)
- **Lenguaje:** Python 3.12
- **Core:** `src/recognizer/core/` — pipeline, puertos, dominio
- **Adaptadores:** `src/recognizer/adapters/` — OpenCV, MediaPipe Python, pynput
- **Capacidad:** Control completo del SO (mouse, teclado, apps, volumen)
- **Distribución:** `uv run` / PyInstaller `.exe`

### Web (`web/`)
- **Lenguaje:** JavaScript vanilla (Vite bundler)
- **Core:** `@mediapipe/tasks-vision` (mismo modelo `.task` que Python)
- **Capacidad:** Solo control dentro de la pestaña (sandbox del navegador)
- **Distribución:** HTML + JS + CSS estático (Vercel / GitHub Pages)

### Qué comparten
- Mismos gestos (8 canned gestures de MediaPipe)
- Mismos umbrales de confianza y estabilización
- Mismo modelo de reconocimiento (`gesture_recognizer.task`)

### Qué es distinto
- **Pointing_Up**: Web = scroll, Desktop = puntero del mouse
- **Thumb_Up**: Web = volumen del video, Desktop = volumen del sistema
- **Victory**: Web = nueva pestaña, Desktop = hotkey
- Desktop tiene acciones que la web no puede hacer (mouse, teclado, apps)

Ver `docs/WEB-PLAN.md` para detalles de la versión web.
