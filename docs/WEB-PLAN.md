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
| `Pointing_Up` | Scroll arriba (continuo al sostener) | Mover puntero del mouse |
| `Thumb_Up` | Subir volumen del video | Subir volumen del sistema |
| `Thumb_Down` | Bajar volumen del video | Bajar volumen del sistema |
| `Closed_Fist` | Scroll abajo (continuo al sostener) | Mute del sistema |
| `Open_Palm` | Play/pause del video | Play/pause multimedia del sistema |
| `Victory` | Cambiar tema claro/oscuro | Enviar hotkey (Ctrl+Shift+M) |
| `ILoveYou` | Siguiente video de la playlist | Abrir enlace con Chrome |

El navegador impone un **sandbox de seguridad** que impide mover el mouse del sistema,
enviar teclas a otras apps, controlar el volumen del sistema o abrir aplicaciones de
escritorio. Por eso la web solo controla contenido **dentro de su propia pestaña**.

Notas:
- `window.open()` (abrir pestañas/enlaces) lo bloquea el navegador cuando no hay un
  clic del usuario: los gestos llegan de forma asíncrona, así que en la web se usan
  solo acciones dentro de la página.
- `OK_Sign` no es un gesto "canned" del modelo de MediaPipe (solo existe en escritorio
  vía reglas geométricas), por eso se quitó de la web.

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
   volumen), scroll en la página (continuo al sostener), cambio de tema y salto de video
   en la playlist del usuario.
5. **Overlay** de landmarks, lateralidad, gesto y FPS en canvas de alto DPI.
6. **Tema claro/oscuro** con persistencia en `localStorage`.
7. **Banner dinámico**: sondea `http://127.0.0.1:8765/health`; si la app de escritorio
   responde, ofrece "Abrir app"; si no, "Descargar para Windows", que enlaza a la última
   release (`github.com/FT-Key/Recognizer/releases/latest`).
8. **Gestos personalizados**: `CONFIG.gestures.customModelUrl` permite cargar un modelo
   `.task` propio (generado con `scripts/train_gesture_model.py`).

## Playlist de YouTube (localStorage)

El usuario agrega sus propios videos y el gesto `ILoveYou` pasa al siguiente.

- Se guarda en `localStorage` (`recognizer-playlist`) **solo el id de 11 caracteres** y un
  titulo en texto plano; nunca la URL ni HTML crudo.
- `lib/playlist.js` valida y normaliza: acepta enlaces de escritorio y moviles
  (`youtube.com/watch`, `m.youtube.com`, `youtu.be`, `/shorts`, `/embed`, `/live`, `/v`,
  `music.youtube.com`) y rechaza cualquier otro host, esquema (`javascript:`) o id
  invalido. Al no persistir URLs no hay superficie de inyeccion.
- El reproductor solo recibe ids ya validados (`loadVideoById`).
- El volumen inicial del reproductor es **50 %** (`CONFIG.video.initialVolume`).

## Diseno (design system Vintage)

La UI sigue el skill `vintage` (`.opencode/skills/vintage/`): superficies plateadas
`#C0C0C0`, acento teal `#008080`, tipografia pixel `Silkscreen` + `JetBrains Mono`,
biseles skeuomorficos y textura con grano/scanlines. Tokens en `src/styles/theme.css`
(claro por defecto + variante oscura para el toggle).

Los iconos son de **Font Awesome 6** via `react-icons` (`src/lib/icons.jsx`): heredan
`currentColor`, asi que siguen el tema y se personalizan desde CSS. Se usan iconos de mano
para los gestos (Open_Palm, Thumb_Up/Down, Closed_Fist, Victory, Pointing_Up, ILoveYou) en
lugar de emojis.

La app tiene dos paginas con router propio por rutas reales (History API, sin
dependencias): **Inicio** (`/`) y **Sobre mi** (`/sobre-mi`). Al cambiar de pagina se sube
al inicio y, al volver a Inicio, el stream de la camara se reengancha al `<video>` (el
estado de la camara se mantiene entre paginas; el worker de gestos sigue vivo).

Para que recargar una ruta como `/sobre-mi` no de 404 en produccion, `web/vercel.json`
reescribe todo a `/index.html` (los archivos estaticos siguen sirviendose normalmente). En
dev y `vite preview` el fallback SPA de Vite ya lo cubre.

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
   es un **worker clásico** (sin imports ESM estáticos) que carga MediaPipe con `import()`
   dinámico desde el CDN (`gestures.moduleUrl`) y deja que use `importScripts()` nativo.
   Así funciona idéntico en `vite dev` y en el build de producción, sin shims.
   (No se usa `@mediapipe/tasks-vision` de npm para evitar que Vite lo empaquete como ESM.)
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
