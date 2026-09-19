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
- `core/ports`: Protocols que el núcleo necesita (`FrameSource`, `HandTracker`, `EventBus`,
  `BrowserTabs`...).
- `core/pipeline`: processors + `PipelineBuilder` (pipes & filters).
- `adapters/`: OpenCV, MediaPipe, pynput, subprocess, persistencia, red (futuro),
  Chromium CDP (`ChromiumCdpBrowser`).
- `settings.py`, `bootstrap.py`, `cli/`: composición y entrada.
- Contratos verificados por import-linter en `pyproject.toml`: el core no importa capas
  externas ni infraestructura; los adapters no importan cli/settings.

## Ejes de cambio previstos (justifican las abstracciones)

1. Fuente de frames: cámara local -> stream web.
2. Destino de acciones: local (SO) -> red/remoto.
3. Identidad: sin enrolamiento -> rol/perfil con permisos.
4. Persistencia: ninguna -> embeddings de rostro / dataset de gestos.
5. Interfaz: overlay OpenCV -> UI de escritorio -> web.
6. Producto: una sola app de gestos -> launcher con varias apps de visión.

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

## Navegador controlado via CDP (etapa 9b)

El puerto `BrowserTabs` (`core/ports/browser_tabs.py`) define `ensure`, `seek_media` y
`press_keys` para controlar pestañas del navegador Chromium. La implementación es
`ChromiumCdpBrowser` (`adapters/chromium_cdp.py`), que usa `CdpClient`
(`adapters/cdp_client.py`) para la comunicación CDP: transporte HTTP (`UrllibCdpTransport`)
para listar/crear targets y transporte WebSocket (`WebsocketCdpTransport`) para comandos
(`Page.navigate`, `Runtime.evaluate`, `Input.dispatchKeyEvent`).

`ChromiumCdpBrowser` auto-detecta el navegador Chromium instalado (Chrome > Edge > Brave >
Vivaldi > Opera > Chromium) via `chromium.py`, lanza una instancia con perfil aislado
(`browser-profile/<familia>/`) en `--remote-debugging-port=9222` si no está corriendo, y
busca pestañas por matching de URL (`TabSpec.match`). Las acciones `open_tab`
(playlist rotatoria via `TabKey`), `tab_seek` (fracción 0..1 de `<video>`) y
`tab_press` (teclas via CDP) se configuran en `config.yaml` bajo `browser.tabs`.

## Gate

`uv run lint` · `uv run typecheck` · `uv run test` (cobertura >= 80%) ·
`uv run check-arch` · `uv run smoke --frames 30 --no-window`.

## Launcher multi-app y modularidad (etapa 10a)

`recognizer` sin argumentos abre un **menú de aplicaciones**; con flags ejecuta la app de
gestos directamente (compatibilidad con scripts y `smoke`). El catalogo de apps es
vocabulario puro del dominio:

- `core/domain/app.py`: `AppId`, `AppInfo` (título, descripción, `implemented`,
  `preparation`), `AppAvailability` y `AppCatalog` (orden, resolución por id/número y
  estado). `AppRunRequest` transporta las opciones comunes de arranque.
- `core/config.py`: `AppsConfig` (`apps.enabled`) es un override de habilitación; solo
  aplica a apps implementadas.
- `cli/menu.py`: render del menú y bucle interactivo (imperative shell). Resuelve el runner
  de cada app de forma **perezosa** dentro de `resolve_runner`.
- `cli/app.py`: `run_gestures(request, ...)` es el runner de gestos; `main` decide entre
  menú (sin args) y ejecución directa.
- `cli/paths.py`: resolución de rutas y modo `frozen` sin importar `cv2`/`mediapipe`, para
  que abrir el menú no cargue librerías de visión.

**Reglas de rendimiento (no negociables):**

1. **Carga perezosa por app.** Cada runner importa sus dependencias pesadas dentro de su
   módulo y solo al lanzarse. Abrir el menú no importa MediaPipe/YOLO ni abre la cámara.
2. **Sin doble procesamiento.** Una app usa una sola vía de inferencia; no se agrega un
   detector de respaldo que reprocese el mismo fotograma (p. ej. MediaPipe + YOLO a la vez).
3. **Salida al menú.** Toda app termina con `ESC`/`q` y devuelve el control al launcher;
   nunca cierra el proceso por sí misma.
4. **Una dependencia pesada por etapa.** Se añade `ultralytics`/`torch` solo cuando exista
   una app que lo use, y se declara en el contrato de import-linter del core.

## Contador de personas con tracking (etapa 10c)

La app del contador usa una sola vía de inferencia: `UltralyticsDetector.track`
(`model.track` con `persist=True` y tracker ByteTrack) cubre detección + tracking, y
`detect` queda como capacidad genérica del puerto `ObjectDetector`. El puerto
`ObjectTracker` (`core/ports/object_tracker.py`) expone `open`/`track`/`close`.

El conteo es dominio puro en `core/domain/tracking.py`: `TrackedDetection` (frozen)
compone `Detection` + `track_id`; `CountingLine` (eje horizontal/vertical y `position`
normalizada) divide el fotograma; `LineCrossingCounter` registra cruces por track con
debounce `confirm_frames` e `invert`, sin importar infraestructura. La línea admite una
banda muerta (hysteresis) `margin` alrededor de `position` que evita cruces fantasma y el
jitter del centro, y `track_timeout_frames` purga el estado de los tracks no vistos para
que un ID muerto no cuente al reaparecer. El overlay vive en `adapters/overlay_people.py`
(`draw_people_overlay`: cajas+ID, línea, banda muerta y HUD). La línea se configura en
`people_counter.line` (`config.yaml`).

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
- **Pointing_Up**: Web = scroll arriba, Desktop = puntero del mouse
- **Thumb_Up**: Web = volumen del video, Desktop = volumen del sistema
- **Victory**: Web = cambiar tema, Desktop = hotkey
- **ILoveYou**: Web = scroll abajo, Desktop = abrir enlace
- **OK_Sign**: solo existe en escritorio (regla de landmarks, no es canned)
- Desktop tiene acciones que la web no puede hacer (mouse, teclado, apps)

Ver `docs/WEB-PLAN.md` para detalles de la versión web.

## Latencia y desacople de inferencia (app facial)

Todas las apps comparten `cli/runtime.run_camera_loop`: lee un fotograma, ejecuta el
pipeline y dibuja. El bucle es **single-thread**: el ritmo de lectura es el ritmo de
inferencia.

- **Apps rápidas** (gestos/MediaPipe, contador/anti-intrusos/postura/YOLO nano): la
  inferencia va a ~10-30 FPS, así que el bucle lee la cámara casi tan rápido como llega el
  stream. Con `CAP_PROP_BUFFERSIZE=1` alcanza para que no haya retraso.
- **App facial** (InsightFace `buffalo_s` en CPU): la inferencia va a ~2-5 FPS. El bucle se
  queda cientos de ms dentro del reconocedor sin leer, **no drena el stream** y la cámara de
  red (teléfono/enlace móvil) acumula retraso hasta segundos; la app de enlace incluso avisa
  *"calidad de red deficiente"*. `CAP_PROP_BUFFERSIZE=1` no lo evita porque ese búfer es
  local; el búfer de red queda del lado del emisor.

Solución en la app facial (solo ella, por ahora):

1. `adapters/latest_frame_source.py` (`LatestFrameSource`): hilo daemon que **drena la
   cámara sin parar** y guarda el último fotograma. `read()` espera al siguiente fotograma
   nuevo y devuelve una copia (para dibujar); `wait_for_new(version)` permite al worker ver
   el último sin consumirlo.
2. `cli/apps/face_auth.py` (`_RecognitionWorker`): hilo que reconoce el último fotograma y
   actualiza el estado (enrolamiento/login) bajo lock. El bucle principal **solo dibuja**,
   así que la vista va a ritmo de cámara aunque la inferencia tarde.
3. `face_auth.det_size` (320 por defecto) y `face_auth.process_every_n_frames` bajan el costo
   de CPU de la inferencia.

**Cuándo aplicar el mismo patrón a otras apps:** cuando la inferencia de una app sea más
lenta que la cámara (FPS de inferencia < FPS de captura) o la cámara sea de red y aparezca
retraso creciente / avisos de calidad. Se hace sin tocar `core`: envolver su `FrameSource`
con `LatestFrameSource` y mover la inferencia a un worker que entregue resultados al bucle
de dibujo. No hace falta para apps que ya corren en tiempo real (hoy, todas menos la facial).

**Para qué sirve:** desacoplar la captura del cómputo. Garantiza (a) que el stream se drene
siempre (sin retraso acumulado ni degradación de red), (b) que el usuario vea video en vivo
con el último resultado disponible, y (c) que subir la carga de inferencia no congele la
interfaz.
