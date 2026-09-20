# Cómo funciona la app de escritorio — Recognizer

Guía para entender el proyecto aunque esté "vibe codeado". Cubre **solo la app de
escritorio** (`src/recognizer/` + `config.yaml`). La versión web (`web/`) es una app
aparte y se explica en `docs/WEB-PLAN.md`.

> Punto de entrada: `uv run recognizer`. Todo lo configurable vive en `config.yaml`
> (única fuente de verdad para umbrales, dispositivos y mapeos gesto → acción).

---

## 1. Qué es y qué hace (en una frase)

Abre tu **cámara**, detecta tus **manos y gestos** con modelos preentrenados de
**MediaPipe**, estabiliza la señal y ejecuta **acciones locales**: teclas multimedia,
atajos, comandos, scripts, enlaces/pestañas del navegador y movimiento del puntero.

```
cámara → frames → [detección + reglas + estabilizador + puntero] → eventos → acciones
```

Comandos típicos:

```powershell
uv run python scripts/download_models.py   # descarga models/*.task (una vez)
uv run recognizer                          # ventana en vivo (ESC/q sale, "a" on/off)
uv run recognizer --no-actions             # solo detectar, sin ejecutar nada
uv run recognizer --no-pointer             # sin mover el cursor
uv run recognizer --no-window --frames 30  # headless (CI / check rápido)
uv run smoke --frames 30 --no-window       # solo mide FPS, sin acciones
```

---

## 2. Arquitectura en 5 minutos (hexagonal + pipeline + bus)

El proyecto usa **arquitectura hexagonal (puertos y adaptadores)**:

- `core/` = lógica pura. **No importa** `adapters/`, `cli/`, `settings/` ni
  `cv2`, `mediapipe`, `pynput`, `yaml`, `fastapi`. Verificado con `uv run check-arch`
  (import-linter, 3 contratos).
- `adapters/` = efectos secundarios (cámara, ML, teclado, mouse, subprocess, red).
- `cli/` + `settings.py` + `bootstrap.py` = *composition root*: leen `config.yaml`,
  crean los objetos e inyectan dependencias **por constructor** (nada de Singletons).

Flujo de datos real (ver `src/recognizer/cli/app.py:main` + `bootstrap.py:build_pipeline`):

1. `OpenCVCamera` entrega un `Frame` (ver `cli/runtime.py:run_camera_loop`).
2. `Pipeline.run(frame)` encadena *processors* (patrón pipes & filters).
3. Los processors publican **eventos frozen** (`core/domain/events.py`) en el
   `InProcessEventBus` (Observer in-process, tipado por clase de evento).
4. Los suscriptores reaccionan: `GestureActionDispatcher` ejecuta acciones,
   `PointerMover`/`PointerClicker` mueven el mouse.
5. `cv2.imshow` dibuja el frame ya anotado por los overlays (el dibujo también son
   processors al final del pipeline).

Pipeline construido en `bootstrap.build_pipeline()` (orden real):

| # | Processor | Qué hace |
|---|-----------|----------|
| 1 | `GestureDetectionProcessor` | Llama al `GestureClassifier` y guarda `hands` + `detections` en el `FrameContext` |
| 2 | `LandmarkRuleProcessor` (si hay `gestures.rules`) | Evalúa reglas geométricas propias sobre los 21 landmarks; compite/complementa al modelo según `rules_priority` |
| 3 | `GestureStabilizerProcessor` | Confirma un gesto tras `stabilization_frames` iguales (default 5) y lo libera tras `release_frames` ausencias (default 5); publica `GestureDetected` / `GestureReleased` / `GestureHeld` |
| 4 | `PointerDetectionProcessor` (+ `PointerClickDetectionProcessor`) | Si el gesto estable es el de activación (`Pointing_Up`) y hay ≤ 1 mano, publica `PointerMoved` (y `PointerClicked` por pinza pulgar-índice) |
| 5 | `LandmarkOverlay` + `GestureOverlay` (+ `MenuOverlay` + `PointerOverlay`) | Dibujan esqueletos, etiqueta, menú y zona del puntero sobre `frame.data` |

Eventos del dominio (`core/domain/events.py`, todos `@dataclass(frozen=True)`):

- `HandsDetected(hands)` — lo que ve el detector este frame (puede ir vacío).
- `GestureDetected(gesture, confidence, handedness)` — gesto **confirmado**.
- `GestureReleased(gesture, handedness)` — se dejó de ver.
- `GestureHeld(...)` — se mantiene pulsado; solo para gestos con `repeat_seconds > 0`
  (p. ej. subir volumen manteniendo `Thumb_Up`).
- `PointerMoved(x, y)` / `PointerClicked` / `PointerReleased`.

El despacho usa `match/case` (ver `core/actions/dispatcher.py:handle`).

---

## 3. Dependencias: qué hay y para qué sirve cada una

`pyproject.toml` (`requires-python = >=3.12,<3.13`, se instala con `uv sync`, nunca
`pip` directo). Plataforma: Windows, Python 3.12 vía `uv`, inferencia en **CPU**
(GPU AMD sin CUDA).

### Runtime (las que usa la app)

| Paquete | Versión aprox. | Para qué se usa en este proyecto |
|---|---|---|
| `mediapipe` | ≥ 1.0.1 | **El cerebro.** `tasks.python.vision.GestureRecognizer` en modo `VIDEO` (`recognize_for_video`). Detecta 21 landmarks por mano + clasifica el gesto. Sin este paquete no hay detección. |
| `opencv-python` (`cv2`) | ≥ 5.0 | **Ojos y pantalla.** `VideoCapture` lee la cámara (`adapters/camera_opencv.py`); `cvtColor` convierte BGR→RGB para MediaPipe; `imshow`/`putText`/`circle` dibujan overlays y HUD. |
| `numpy` | ≥ 2.5.3 | El `Frame.data` es un `NDArray[np.uint8]` (imagen H×W×3). OpenCV y MediaPipe intercambian imágenes como arrays numpy. |
| `pydantic` + `pydantic-settings` | ≥ 2.13 / 2.15 | **Validación de `config.yaml`.** `core/config.py` define `AppConfig`, `GestureConfig`, `PointerConfig`, `*ActionConfig`… Modelos `frozen`, `extra="forbid"`: si escribes mal una clave o un gesto no existe en el catálogo, la app falla al arrancar con `ConfigError` en vez de fallar a mitad. |
| `pyyaml` | ≥ 6.0.3 | Lee `config.yaml` (`settings.py:load_config` con `yaml.safe_load`). |
| `pynput` | ≥ 1.8.2 | **Manos de la app.** `keyboard.Controller` pulsa teclas multimedia y hotkeys (`adapters/pynput_keys.py`); `mouse.Controller` mueve el cursor y hace click (`adapters/pynput_mouse.py`). |
| `websocket-client` | ≥ 1.8.0 | Transporte WebSocket para hablar **CDP** con Chromium (`adapters/cdp_client.py:WebsocketCdpTransport`). Solo se usa si configuras acciones `open_tab`/`tab_seek`/`tab_press`. |
| `tkinter` (stdlib, no está en el toml) | — | Solo para **medir la pantalla** (`winfo_screenwidth/height` en `adapters/pynput_mouse.py`). Ojo histórico: el `.exe` de PyInstaller no lo incluía y el puntero moría; ya está añadido al bundle. |

### Dev / calidad (grupo `dev`)

| Paquete | Para qué |
|---|---|
| `pytest` + `pytest-cov` | Tests. Cobertura mínima **80%** (`uv run test`). Los tests que tocan hardware real se marcan `@pytest.mark.integration` y se excluyen por defecto. |
| `ruff` | Lint + formato (`uv run lint`). Reglas: `ANN` (todo tipado), `S` (nada de `shell=True`), `T20` (prohibido `print`, usa `logging`), etc. |
| `mypy --strict` | Tipado estricto (`uv run typecheck`). **Cero `typing.Any`** en código propio; en la frontera con `cv2/mediapipe/pynput` se usa `Protocol` + `cast` documentado. |
| `import-linter` | Contratos de capas (`uv run check-arch`). |
| `pyinstaller` | Empaqueta `dist/Recognizer/` con `scripts/build_exe.py` (ver `docs/DESKTOP-APP-PLAN.md`). |
| `types-pyyaml` | Stubs para que mypy entienda `yaml`. |

---

## 4. Modelos preentrenados: de dónde vienen y qué son

### 4.1. Descarga

```powershell
uv run python scripts/download_models.py
```

Descarga de `https://storage.googleapis.com/mediapipe-models/...` (bucket oficial de
Google) a `models/`:

| Archivo | URL origen | Qué es | Tamaño aprox. |
|---|---|---|---|
| `hand_landmarker.task` | `.../hand_landmarker/hand_landmarker/float16/latest/...` | Localiza manos y devuelve **21 landmarks 3D normalizados** por mano + lateralidad (Left/Right) | ~10 MB |
| `gesture_recognizer.task` | `.../gesture_recognizer/gesture_recognizer/float16/latest/...` | Hace lo anterior **más clasificación** del gesto (incluye el landmarker dentro). **Es el que usa la app** | ~15 MB |
| `blaze_face_short_range.tflite` | `.../face_detector/blaze_face_short_range/float16/latest/...` | Detector facial ligero. **Descargado pero aún sin usar** (reservado para etapa 10: enrolamiento facial) | ~2 MB |

`.task` = *bundle* de MediaPipe (modelo TFLite + metadatos empaquetados). `float16` =
pesos en media precisión: ocupa la mitad y corre bien en CPU.

**No entrenamos nada**: son modelos cerrados entrenados por Google con miles de
imágenes de manos. Nosotros solo hacemos **inferencia** (les pasamos un frame, nos
devuelven landmarks + etiqueta + score 0..1).

### 4.2. Qué gestos reconoce el modelo de serie

El `gesture_recognizer.task` oficial distingue **7 gestos + `None`** (nada reconocible).
Están en `core/domain/gesture.py`:

`Closed_Fist`, `Open_Palm`, `Pointing_Up`, `Thumb_Down`, `Thumb_Up`, `Victory`,
`ILoveYou` (+ `None`).

### 4.3. Cómo se usan en código

`adapters/mediapipe_gesture_classifier.py` (`MediaPipeTasksGestureFacade`):

1. `open()` → `vision.GestureRecognizer.create_from_options(...)` con
   `running_mode=VIDEO`, `num_hands`, y los tres umbrales de `config.yaml`
   (`min_hand_detection_confidence`, `min_hand_presence_confidence`,
   `min_tracking_confidence`).
2. Por frame: convierte BGR→RGB (`cv2.cvtColor`), lo envuelve en `mp.Image(SRGB)` y
   llama a `recognize_for_video(image, timestamp_ms)`.
3. Mapea la respuesta a dominio propio: `HandLandmarks(handedness, confidence,
   points)` + `DetectedGesture(name, confidence, handedness)`. Si la etiqueta no está
   en el catálogo permitido (`CANNED + custom_labels`), se degrada a `None`.
4. `swap_handedness` (config) invierte Left/Right si tu cámara espeja la imagen.

Los 21 landmarks siguen el estándar MediaPipe (0 = muñeca, 8 = punta del índice,
etc.; índices con nombre en `core/domain/hand.py`: `WRIST_LANDMARK_INDEX`,
`INDEX_FINGER_TIP_LANDMARK_INDEX`…).

### 4.4. Cómo crear/entrenar tus propios gestos (dos vías, sin tocar Python)

**Vía A — Reglas geométricas (recomendada, sin entrenar).** Declaras el gesto en
`config.yaml` → `gestures.rules`. Ejemplo real (el `OK_Sign` que trae el proyecto):

```yaml
gestures:
  rules:
    OK_Sign:
      extended: [middle, ring, pinky]
      folded: [index]
      distance: {a: thumb, b: index, max_ratio: 0.35}
```

El motor (`core/pipeline/landmark_rules.py`, core puro sin dependencias) comprueba:
dedos extendidos/doblados (ángulo > `straight_angle_deg`, default 160°), dirección de
un dedo (8 sentidos), ángulo entre dos dedos y distancia normalizada por tamaño de
mano (invariante a qué tan lejos estés). `rules_priority: rules_first | model_first`
decide quién gana si regla y modelo discrepan.

**Vía B — Modelo custom con Model Maker (reentrenamiento real).** Script
`scripts/train_gesture_model.py`:

1. Armas un dataset: una carpeta por gesto con fotos (`dataset/mi_gesto_a/*.jpg`).
2. `uv run python scripts/train_gesture_model.py --dataset dataset --epochs 10`
   (requiere `scripts/requirements-model-maker.txt`: TensorFlow; en Windows se
   recomienda WSL).
3. Internamente: `Dataset.from_folder` → split 80/10/10 → `GestureRecognizer.create`
   (fine-tuning del clasificador sobre los embeddings de landmarks) → `evaluate`
   (loss/accuracy) → exporta `models/custom_gesture_recognizer.task`.
4. En `config.yaml`: `gestures.model_path: models/custom_gesture_recognizer.task` y
   declara las etiquetas nuevas en `gestures.custom_labels: [mi_gesto_a, ...]`.
   El adaptador las acepta y el `GestureCatalog` las valida; luego se mapean en
   `actions.mappings` como cualquier gesto de serie.

---

## 5. Funciones Python clave (dónde mirar según qué quieras tocar)

### Arranque y bucle

- `cli/app.py:main()` — entrypoint `recognizer`. Parsea flags (`--no-actions`,
  `--no-pointer`, `--no-browser`, `--device`, `--frames`, `--no-window`,
  `--health-port`, `--verbose`), carga config, crea bus + dispatcher + puntero +
  clasificador + pipeline, abre cámara y modelo con `ExitStack`, corre
  `run_camera_loop`, imprime el resumen final (frames, FPS, gestos confirmados).
  La tecla `a` alterna el `ActionGate` (HUD verde/rojo vía `cv2.putText`).
- `cli/runtime.py:run_camera_loop()` — `camera.read()` → `pipeline.run(frame)` →
  `imshow`. Corta por ESC/q o `--frames N`; si la cámara falla 30 lecturas seguidas
  lanza `CameraError`. Devuelve `(frames, fps_medios)`.
- `cli/smoke.py` — variante mínima sin acciones (solo FPS).
- `settings.py:load_config()` — lee y valida el YAML con pydantic; traduce errores a
  `ConfigError`.
- `bootstrap.py` — `build_pipeline()`, `build_action_bindings()`,
  `build_pointer_mover()/build_pointer_clicker()`, `resolve_camera_config()`.

### Cámara (`adapters/camera_opencv.py`)

`OpenCVCamera.open()` (fija resolución/FPS con `capture.set`), `.read()` → `Frame`
o `None` si falla el frame, `.release()`, `__enter__/__exit__`. Acepta
`capture_factory` inyectable para tests sin cámara real.

### Clasificador (`adapters/mediapipe_gesture_classifier.py`)

`MediaPipeGestureClassifier` (puerto `GestureClassifier`) delega en
`MediaPipeTasksGestureFacade`: `open()` / `classify(frame)` / `close()`. Funciones
de mapeo `_to_mp_image`, `_map_hand`, `_map_gesture`, `_map_result`.

### Estabilizador (`core/pipeline/gesture_stabilization.py`)

`GestureStabilizerProcessor.process()`: por lateralidad (Left/Right) cuenta frames
del candidato; confirma con N iguales, libera con M ausencias, filtra por
`min_gesture_confidence` y emite `GestureHeld` periódico si hay `repeat_seconds`.

### Acciones (`core/actions/` + `adapters/pynput_*`, `subprocess_*`, `chromium_cdp.py`)

- `dispatcher.py:GestureActionDispatcher.handle()` — primero intenta **menú compuesto**
  (`find_menu_match`), si no, **mapeo global**; fallback `NoOpAction`. Un `ActionError`
  loguea warning; una excepción inesperada loguea pero **no tumba la app**.
- Tipos (`config.yaml → core/config.py → bootstrap._build_action`):
  `media_key` (volumen, play/pausa…), `hotkey` (p. ej. `ctrl+shift+m`),
  `command` (argv sin shell), `script` (`.py/.ps1/.bat/.cmd/.sh`, bloqueante con
  timeout o en segundo plano, contexto opt-in `RECOGNIZER_*`), `open_links`
  (playlist secuencial rotatoria en Chrome), `open_tab` / `tab_seek` / `tab_press`
  (navegador propio controlado por **CDP**: `ChromiumCdpBrowser` lanza Chromium con
  perfil aislado `browser-profile/<familia>/` en puerto 9222 y envía
  `Page.navigate`, `Runtime.evaluate`, `Input.dispatchKeyEvent`).
- Decoradores (`decorators.py`): toda acción real se envuelve en
  `Gated(Debounced(Logged(action)))` — `Logged` deja traza, `Debounced` respeta
  `cooldown_seconds` (default 1 s), `Gated` comparte el interruptor on/off.
- `menus.py:HandGestureTracker` + `find_menu_match` — con 2 manos, una sostiene el
  modificador (`hand: Left, modifier: Pointing_Up`) y la otra elige opción; con
  `consume_trigger: true` la opción no dispara además su acción global
  (anti-repetición incluida).

### Puntero virtual (`core/pointer/` + `core/pipeline/pointer_detection.py`)

`PointerDetectionProcessor`: si el gesto estable es `activation_gesture`
(`Pointing_Up`) y hay ≤ 1 mano, proyecta la punta del índice (landmark 8) de la
**zona activa** (`0.2–0.8`, `mirror_x: true`) a pantalla completa y publica
`PointerMoved`. `PointerMover` lo suscribe y `PynputMouseController.move_to` lo mueve
(suavizado `none`/`ema`, `alpha: 0.35`); la pinza pulgar-índice publica
`PointerClicked` (click izquierdo). Tamaño de pantalla vía `tkinter`.

### Configuración (`config.yaml` + `core/config.py` + `core/constants.py`)

Secciones: `camera`, `hands`, `gestures` (modelo, estabilizador, `swap_handedness`,
`custom_labels`, `rules_priority`, `rule_thresholds`, `rules`), `pointer`
(`activation_gesture`, `mirror_x`, `smoothing`, `active_zone`…), `actions`
(`cooldown_seconds`, `mappings`, `menus`), `browser` (`executable`, `debugging_port`,
`tabs`). Regla del proyecto: **cero números/strings mágicos** en código — los
defaults viven en `core/constants.py`, lo ajustable en `config.yaml`.

---

## 6. Gate de calidad y flujo de trabajo (para no romper nada)

```powershell
uv run lint        # ruff check + format (109+ archivos)
uv run typecheck   # mypy --strict (sin Any)
uv run test        # pytest, cobertura >= 80%
uv run check-arch  # import-linter 3/3
uv run smoke --frames 30 --no-window
```

Todo cambio de comportamiento lleva tests (sin hardware real). Ramas
`stage/<n>-<slug>` desde `dev`, merge `--no-ff` a `dev`; `main` solo se mergea en
GitHub. Estado vivo en `docs/STATE.md`; historial por etapa en `docs/history/`.

## 7. Mapa rápido de archivos (desktop)

```
config.yaml                  ← lo único que edita un usuario normal
models/*.task                ← modelos descargados / entrenados
scripts/download_models.py   ← descarga oficial de Google
scripts/train_gesture_model.py ← fine-tuning de gestos propios
src/recognizer/cli/app.py    ← main: compone todo y corre el loop
src/recognizer/cli/runtime.py← bucle cámara + ventana + FPS
src/recognizer/bootstrap.py  ← factories: pipeline, acciones, puntero
src/recognizer/settings.py   ← carga YAML → AppConfig
src/recognizer/core/config.py← esquema pydantic de toda la config
src/recognizer/core/domain/  ← Frame, Hand, Gesture, Events, Action (frozen)
src/recognizer/core/pipeline/← processors + builder + context
src/recognizer/core/actions/ ← dispatcher, menús, decoradores, acciones puras
src/recognizer/core/pointer/ ← mover, clicker, suavizado (ema/none)
src/recognizer/adapters/     ← camera_opencv, mediapipe_*, pynput_*, subprocess_*,
                               chromium_cdp, cdp_client, overlay_opencv, health_server
```
