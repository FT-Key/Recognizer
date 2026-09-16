# Etapa 9 — App web (React) + empaquetado de escritorio (PyInstaller)

- **Rama:** `dev` (trabajo directo, sin rama `stage/*`)
- **Estado:** implementada (sin merge; verificación manual de cámara pendiente)
- **Objetivo:** materializar la doble entrega de Recognizer: una **app web** que corre
  en el navegador (sandbox) y un **ejecutable de escritorio** con control completo de la
  PC, compartiendo el mismo modelo de gestos pero con implementaciones y acciones
  distintas.

## Criterios de aceptación
- App web migrada a **React + Vite** con la lógica pura separada de la UI. ✅
- MediaPipe corre en un **Web Worker** (no bloquea el hilo de UI), con fallback GPU→CPU. ✅
- Estabilización, acciones de YouTube y navegación funcionando. ✅
- **Tema claro/oscuro** persistente. ✅
- **Banner dinámico** que detecta la app de escritorio vía endpoint local de salud. ✅
- **Gestos personalizados**: script de entrenamiento (Model Maker) y soporte en la web. ✅
- **PyInstaller** empaqueta solo el escritorio (`dist/Recognizer/`) en modo onedir. ✅
- Gate verde (lint, mypy, pytest, check-arch) y `npm run build` OK. ✅

## Cambios (archivos)

### Web (`web/`, migración a React)
- `index.html`, `package.json`, `vite.config.js`: React 19 + `@vitejs/plugin-react`,
  worker en formato ES, dependencia `@mediapipe/tasks-vision@0.10.18`.
- `src/lib/*`: `config`, `stabilizer`, `actions`, `navigation`, `youtube-controller`,
  `landmarks` (lógica pura, sin React).
- `src/workers/gesture.worker.js`: MediaPipe en worker; recibe `ImageBitmap` por frame.
- `src/hooks/*`: `useCamera`, `useGestureEngine`, `useYouTube`, `useTheme`,
  `useDesktopApp`.
- `src/components/*`: `Header`, `CameraPanel`, `GestureDisplay`, `VideoPanel`,
  `GestureMap`, `DownloadBanner`, `ActionFeedback`.
- `src/styles/*`: `theme.css` (variables por tema), `app.css`.
- Eliminados los `js/` y `css/` de la versión vanilla anterior.

### Escritorio
- `src/recognizer/adapters/health_server.py` (nuevo): servidor de salud en loopback con
  CORS y cabecera Private Network Access.
- `src/recognizer/cli/app.py`: `--health-port` (default 8765 en frozen, 0 en fuente),
  `_is_frozen`/`_default_config_path`/`_prepare_workspace` para resolver rutas junto al
  `.exe` y fijar el CWD; arranque/parada del servidor de salud.
- `packaging/entrypoint.py` (nuevo): punto de entrada para PyInstaller.
- `packaging/recognizer.spec` (nuevo): spec onedir; `collect_all("mediapipe")`,
  `collect_submodules("pynput")`; **no** excluye matplotlib.
- `scripts/build_exe.py` (nuevo): compila y copia `config.yaml`, `models/`,
  `scripts/actions/` junto al `.exe`.
- `scripts/train_gesture_model.py` + `scripts/requirements-model-maker.txt` (nuevos):
  entrenamiento de gestos personalizados con Model Maker.
- `pyproject.toml`: `pyinstaller` en el grupo dev.
- `tests/unit/test_health_server.py` (nuevo) y ampliación de `test_app_cli.py`.

### Docs
- `docs/WEB-PLAN.md`, `docs/DESKTOP-APP-PLAN.md` reescritos al estado real.
- `docs/history/index.md` y `docs/STATE.md` actualizados.

## Decisiones
- **React (JSX, sin TypeScript)** para la web: componentes y hooks, con la lógica de
  dominio en `src/lib` para poder testearla/migrarla sin React.
- **Web Worker** para MediaPipe: la inferencia bloqueaba el hilo de UI; ahora el hilo
  principal solo transfiere frames y dibuja.
- **App web independiente del escritorio**: comparten el modelo, no la implementación de
  acciones. El build de PyInstaller solo incluye `src/recognizer` (nunca `web/`).
- **onedir** en PyInstaller (no onefile) por estabilidad de MediaPipe.
- **Detección de escritorio por endpoint local** (no hay forma de detectar apps
  instaladas desde el navegador por seguridad). Si el sondeo falla, el banner degrada a
  "Descargar app".
- **Recursos editables fuera del binario** (config/models/scripts) para no recompilar.

## Tests y gate (resultados reales)
- `uv run lint`: ruff check OK; ruff format OK (143 archivos).
- `uv run typecheck`: mypy strict OK (107 archivos).
- `uv run test`: **492 passed**, 2 deselected, cobertura **98.38%**.
- `uv run check-arch`: **3/3** contratos KEPT.
- `npm run build` (web): OK — worker aislado (~133 kB), bundle ~239 kB.
- `scripts/build_exe.py`: build OK; `dist/Recognizer/` ~261 MB.
- `.exe` verificado: `--help`, `--no-window --frames 3` (carga MediaPipe y procesa
  frames) y `GET /health` responde `{"app":"recognizer",...}`.

## Correcciones post-implementación (bug del .exe)
- **Síntoma:** el `.exe` abría ventana, `ILoveYou` funcionaba, pero `Pointing_Up` no movía
  el puntero y la app se cerraba sola a los pocos segundos.
- **Causa raíz:** el `.spec` excluía `tkinter`, pero
  `adapters/pynput_mouse.py::_default_screen_size()` lo importa para resolver el tamaño de
  pantalla del puntero. En el `.exe`, `import tkinter` lanzaba `ModuleNotFoundError`, que
  no estaba capturado (`move_to` solo capturaba `OSError/ValueError/RuntimeError`) y se
  propagaba hasta tumbar el bucle de cámara.
- **Arreglos:**
  - `packaging/recognizer.spec`: se deja de excluir `tkinter` (bundle +24 MB).
  - `adapters/pynput_mouse.py`: se captura también `ImportError` → `ActionError`; nuevo
    helper público `screen_size()`.
  - `core/pointer/mover.py` y `core/actions/dispatcher.py`: un error inesperado se
    registra con traza (`logger.exception`) y **no** propaga (frontera de robustez).
  - `cli/app.py`: logging a `logs/recognizer.log` junto al `.exe` (`--log-file`),
    `sys.excepthook` + `threading.excepthook` para capturar crashes, y log de
    "Pantalla detectada: WxH" al arrancar el puntero.
- **Verificación:** `.exe` reconstruido; el log muestra `Pantalla detectada: 1920x1080`
  (tkinter operativo en el bundle) y la ejecución headless termina limpia. Tests: 504
  passed, 98.54%.

## Correcciones post-deploy (app web)
Tras desplegar en Vercel y probar con cámara real aparecieron tres fallos:
- **No se reconocía ningún gesto / no había landmarks.** Causa: MediaPipe carga su WASM
  con `importScripts()`, prohibido en Web Workers de tipo `module` (`Module scripts don't
  support importScripts()`), así que el worker fallaba al iniciar. Solución: shim de
  `importScripts` (XHR síncrono + `eval`) en `src/workers/gesture.worker.js`; funciona en
  dev y en producción. Además se muestra un banner de error en la UI y se loguea en
  consola el error del worker.
- **Solo funcionaba `Open_Palm`.** Causa: el estabilizador web reiniciaba el buffer cada
  frame al ver un gesto distinto del confirmado, de modo que ningún otro gesto llegaba a
  confirmarse ni el anterior se liberaba. Solución: reescrito `src/lib/stabilizer.js` con
  la semántica del `GestureStabilizerProcessor` (candidato N frames, liberación M frames,
  reemplazo con `Release`+`Detected`). Verificado con un script Node.
- **Overlay espejado.** Causa: el video se voltea con CSS (`scaleX(-1)`) pero el canvas
  dibujaba los landmarks en coordenadas sin espejar. Solución: `landmarks.js` invierte `x`.
- **Textos con `\uXXXX` literales** (`Acci\u00F3n`, `C\u00E1mara`): eran escapes dentro de
  nodos de texto JSX. Reemplazados por caracteres UTF-8 reales.
- Extra: solo los gestos con `repeat: true` (volumen) se re-disparan al sostenerse.

### Latencia (segundos de retraso) y ajuste de gestos
- **Síntoma:** el overlay seguía la mano con segundos de retraso. Medido con Playwright:
  la inferencia tarda ~90 ms/frame (~11 fps) y el hilo principal enviaba frames a 60 fps
  sin límite → la cola de mensajes del worker crecía sin control.
- **Causa y arreglo:** faltaba *backpressure*. Ahora se envía **como mucho un frame en
  vuelo** (`frameInFlight`) y no se envía nada hasta que el worker responde `ready` (si no,
  un frame descartado durante la carga dejaba la cola bloqueada). El worker responde
  siempre a cada frame para no romper el backpressure.
- **Worker:** se pasa a worker **clásico** con `import()` dinámico de MediaPipe desde el CDN
  (`gestures.moduleUrl`), eliminando el shim de `importScripts` y la dependencia npm
  `@mediapipe/tasks-vision`. Funciona igual en dev y producción.
- **Mapeos web ajustados:** `Pointing_Up` → scroll arriba y `ILoveYou` → scroll abajo
  (ambos continuos al sostener); `Victory` → cambiar tema claro/oscuro; se quita `OK_Sign`
  (no es gesto canned del modelo). Se descartan `new_tab`/`open_url` porque `window.open()`
  sin clic del usuario lo bloquea el navegador.

## Rediseño de la web (design system Vintage) + playlist

- **Skill de diseño:** se incorporó `.opencode/skills/vintage/` (SKILL.md + DESIGN.md,
  autor typeui.sh, MIT) y se aplicaron sus tokens: plateado `#C0C0C0`, teal `#008080`,
  tipografía pixel `Silkscreen` + `JetBrains Mono`, biseles skeuomórficos, textura con
  grano y scanlines. Tokens en `src/styles/theme.css` (claro por defecto + oscuro).
- **Dos páginas** con router por hash (`useHashRoute`, sin dependencias): **Inicio** y
  **Sobre mí** (navbar + footer nuevos). Al salir de Inicio se apaga la cámara.
- **Playlist de YouTube:** `lib/playlist.js` sanitiza enlaces (escritorio y móvil) y
  guarda en `localStorage` solo `{id, title}`; `PlaylistManager` permite agregar/quitar y
  elegir el video actual; el gesto `ILoveYou` pasa al siguiente.
- **Gestos web ajustados:** `Closed_Fist` → scroll abajo y `ILoveYou` → siguiente video
  (antes mute y scroll). `Victory` sigue cambiando el tema.
- **Volumen inicial del reproductor: 50 %** (`CONFIG.video.initialVolume`).
- **Contenido nuevo en Inicio** (hero, características, cómo funciona, FAQ, banner de
  descarga) y página **Sobre mí** con foto (placeholder en `web/public/franco.jpg`), bio,
  habilidades, trayectoria, proyectos y portfolio.

### Ajustes de layout y navegacion
- **Orden de la pagina:** la demo (camara + video lado a lado) va primero, con el mapa de
  gestos debajo del video (columna derecha); despues el intro (hero mas discreto, en panel,
  conservando todo el texto) y el resto de secciones.
- **Router por rutas reales** (History API) en vez de hash: `/` y `/sobre-mi`, con scroll
  al inicio al cambiar de pagina. `web/vercel.json` reescribe todo a `index.html` para que
  recargar `/sobre-mi` no de 404.
- **La camara persiste entre paginas:** ya no se apaga al salir de Inicio; al volver se
  reengancha el stream al `<video>` y el worker de gestos sigue vivo (no re-inicializa).

## Pendientes / riesgos
- Verificación manual con cámara real de la web (gestos, YouTube, tema, banner) y del
  `.exe` con ventana (overlay, acciones).
- El sondeo a `http://127.0.0.1` desde HTTPS depende de Private Network Access; el banner
  degrada con gracia.
- El entrenamiento con `mediapipe-model-maker` requiere TensorFlow (usar WSL/Linux).
- Deploy de la web a Vercel/GitHub Pages: pendiente de decidir dominio.
