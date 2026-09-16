# Plan web — Recognizer Web v2 (React)

## Arquitectura dual

Recognizer tiene **dos aplicaciones distintas** que comparten el mismo modelo de
reconocimiento de gestos pero son implementaciones independientes:

| | **Web** (`web/`) | **Desktop** (`src/recognizer/`) |
|---|---|---|
| **Lenguaje** | React 19 + Vite (JS/JSX) | Python 3.12 |
| **Reconocimiento** | MediaPipe Tasks Vision (JS, en Web Worker) | MediaPipe Tasks (Python) |
| **Cámara** | `getUserMedia()` | OpenCV `VideoCapture` |
| **Ejecución** | Browser sandbox | Sistema operativo completo |
| **Deploy** | Vercel / GitHub Pages (estático) | PyInstaller `.exe` (`scripts/build_exe.py`) |
| **Capacidad** | Controla la pestaña/iframe | Controla la PC completa |

### Comportamientos distintos por gesto (mismo gesto, distinta acción)

| Gesto | Web (sandbox) | Desktop (SO completo) |
|---|---|---|
| `Pointing_Up` | Scroll arriba en la página | Mover puntero del mouse |
| `Thumb_Up` | Subir volumen del video embebido | Subir volumen del sistema |
| `Thumb_Down` | Bajar volumen del video embebido | Bajar volumen del sistema |
| `Closed_Fist` | Mute del video embebido | Mute del sistema |
| `Open_Palm` | Play/pause del video embebido | Play/pause multimedia del sistema |
| `Victory` | Abrir nueva pestaña | Enviar hotkey (Ctrl+Shift+M) |
| `ILoveYou` | Abrir enlace en nueva pestaña | Abrir enlace con Chrome |
| `OK_Sign` | Scroll abajo en la página | (personalizable) |

El navegador impone un **sandbox de seguridad** que impide mover el mouse del sistema,
enviar teclas a otras apps, controlar el volumen del sistema o abrir aplicaciones de
escritorio. Por eso la web solo controla contenido **dentro de su propia pestaña**.

## Estructura de la app web (React)

```
web/
├── index.html                    # div#root + /src/main.jsx
├── package.json                  # react, react-dom, @mediapipe/tasks-vision, vite
├── vite.config.js                # plugin-react + worker format es
└── src/
    ├── main.jsx                  # createRoot
    ├── App.jsx                   # orquesta hooks y compone paneles
    ├── lib/                      # lógica pura, sin React
    │   ├── config.js             # umbrales, mappings, theme, desktop probe
    │   ├── stabilizer.js         # estabilización N/M frames
    │   ├── actions.js            # dispatcher gesto→acción + cooldown
    │   ├── navigation.js         # abrir pestañas, scroll
    │   ├── youtube-controller.js # YouTube IFrame API
    │   └── landmarks.js          # dibujo de landmarks/HUD en canvas
    ├── workers/
    │   └── gesture.worker.js     # MediaPipe fuera del hilo de UI
    ├── hooks/
    │   ├── useCamera.js          # getUserMedia + dispositivos
    │   ├── useGestureEngine.js   # worker + estabilizador + dibujo (rAF)
    │   ├── useYouTube.js         # carga de la IFrame API
    │   ├── useTheme.js           # tema claro/oscuro persistente
    │   └── useDesktopApp.js      # sondeo de la app de escritorio
    ├── components/               # Header, CameraPanel, VideoPanel, GestureMap,
    │   └── ...                   # DownloadBanner, GestureDisplay, ActionFeedback
    └── styles/
        ├── theme.css             # variables :root[data-theme]
        └── app.css               # layout y componentes
```

## Capacidades implementadas (v2)

1. **Cámara** con selección de dispositivo (`getUserMedia`).
2. **Reconocimiento en Web Worker**: MediaPipe no bloquea el hilo de UI.
   - GPU con fallback automático a CPU si el delegate GPU falla.
   - El hilo principal transfiere `ImageBitmap` por frame (`requestAnimationFrame`).
3. **Estabilización** idéntica a la app de escritorio (N=5 confirmación, M=5 liberación).
4. **Acciones del navegador**: control de un video YouTube embebido (play/pause,
   volumen, mute) y navegación (nueva pestaña, scroll).
5. **Overlay** de landmarks, lateralidad, gesto y FPS en canvas de alto DPI.
6. **Tema claro/oscuro** con persistencia en `localStorage`.
7. **Banner dinámico**: sondea `http://127.0.0.1:8765/health`; si la app de escritorio
   responde, ofrece "Abrir app"; si no, "Descargar app".
8. **Gestos personalizados**: `CONFIG.gestures.customModelUrl` permite cargar un modelo
   `.task` propio (generado con `scripts/train_gesture_model.py`).

## Detección de la app de escritorio

La app de escritorio expone un endpoint local de salud con
`recognizer --health-port 8765` (activo por defecto en el `.exe`). La web lo sondea:

```
Web (HTTPS) ──fetch──> http://127.0.0.1:8765/health
   respuesta OK  -> banner "Abrir app"   (+ badge "Detectada en este equipo")
   sin respuesta -> banner "Descargar app"
```

Notas:
- El servidor escucha solo en loopback y expone únicamente `GET /health`.
- Se envía `Access-Control-Allow-Origin: *` y
  `Access-Control-Allow-Private-Network: true` para el preflight de Chrome (PNA).
- Si el navegador bloquea la petición a localhost, el banner cae a "Descargar app".

## Gestos personalizados (MediaPipe Model Maker)

```bash
# 1. Instalar dependencias de entrenamiento (aparte del proyecto)
uv pip install -r scripts/requirements-model-maker.txt

# 2. Preparar dataset: una carpeta por gesto con imágenes
#    dataset/mi_gesto_a/*.jpg, dataset/mi_gesto_b/*.jpg, ...

# 3. Entrenar y exportar models/custom_gesture_recognizer.task
uv run python scripts/train_gesture_model.py --dataset dataset --epochs 10
```

Luego, en `web/src/lib/config.js`, define
`gestures.customModelUrl` (ruta local en `public/` o URL). El modelo sustituye al de
Google. En escritorio, cambia `gestures.model_path` y declara `gestures.custom_labels`
en `config.yaml`.

> `mediapipe-model-maker` depende de TensorFlow y puede no instalarse en Windows;
> usa WSL o Linux/macOS para el entrenamiento.

## Build y deploy

```bash
cd web
npm install
npm run dev          # http://localhost:5173
npm run build        # web/dist/ (estático)
npx vercel --prod    # o conectar el repo a Vercel
```

`getUserMedia` exige contexto seguro (HTTPS o localhost); Vercel/GitHub Pages lo dan.

## Problemas conocidos y soluciones (MediaPipe en el navegador)

1. **`importScripts` en Web Workers de módulo.** MediaPipe carga su WASM con
   `importScripts()`, que existe en un worker de tipo `module` pero lanza
   `Module scripts don't support importScripts()`. Solución: `src/workers/gesture.worker.js`
   instala un shim que reemplaza `importScripts` por una carga síncrona (XHR + `eval`),
   que es lo que hace internamente. Así funciona igual en `vite dev` (worker módulo) y en
   el build de producción.
2. **Overlay espejado.** El `<video>` se muestra espejado (selfie) con `scaleX(-1)`, pero
   los landmarks llegan en el espacio de la imagen original. Solución: `landmarks.js`
   invierte `x` (`1 - x`) al dibujar geometría; el texto se mantiene legible.
3. **Gestos que no cambian.** El estabilizador debe permitir que un gesto distinto
   reemplace al confirmado tras N frames (publicando la liberación del anterior). Un
   estabilizador que solo libera por ausencia deja la app clavada en el primer gesto.
   Ver `src/lib/stabilizer.js` (misma semántica que `GestureStabilizerProcessor`).
4. **Acciones repetidas al mantener un gesto.** Solo los gestos marcados con
   `repeat: true` (volumen) se re-disparan mientras se sostienen; el resto ejecuta una vez
   al confirmarse.

## Verificación local

```bash
npm run dev      # http://localhost:5173
npm run build && npm run preview   # build de producción en http://localhost:4173
```

Ambos modos deben mostrar `Listo · GPU` (o `CPU`) y dibujar los landmarks al mostrar la
mano. Si aparece un banner rojo de error, el mensaje indica la causa.

## Riesgos

- **Privacidad**: el video se procesa localmente; no se sube a ningún servidor.
- **CDN**: el WASM de MediaPipe y el modelo `.task` se cargan desde CDN de Google.
- **Performance**: en equipos antiguos, usar el delegate CPU si GPU falla.
- **PNA (Private Network Access)**: el sondeo a localhost puede requerir permisos del
  navegador en el futuro; el banner degrada con gracia a "Descargar app".
