# Recognizer Web

App web (React + Vite) que reconoce gestos de mano con la cámara y controla el
navegador. Corre **100% en el cliente**: la inferencia es local (MediaPipe en un Web
Worker) y no se sube video a ningún servidor.

> Es una app **distinta** de la de escritorio. Comparten el modelo de gestos, no las
> acciones: la web está limitada por el sandbox del navegador (controla la pestaña; no
> puede mover el mouse del sistema ni abrir apps). Para control total, usa la app de
> escritorio (ver `docs/DESKTOP-APP-PLAN.md`).

## Requisitos

- Node.js 18+
- Un navegador con cámara (Chrome/Edge recomendados)
- Contexto seguro: `https://` o `http://localhost` (lo exige `getUserMedia`)

## Desarrollo

```bash
npm install
npm run dev        # http://localhost:5173
```

Acepta el permiso de cámara y pulsa **Activar cámara**.

## Build y deploy

```bash
npm run build      # genera dist/ (estático)
npm run preview    # sirve dist/ en local
```

Deploy estático en Vercel:

```bash
npx vercel --prod
```

O conecta el repositorio a Vercel/GitHub Pages apuntando al directorio `web/`.

## Gestos

| Gesto | Acción |
|---|---|
| `Open_Palm` | Play / Pause del video |
| `Thumb_Up` | Subir volumen |
| `Thumb_Down` | Bajar volumen |
| `Closed_Fist` | Mute |
| `Victory` | Nueva pestaña |
| `Pointing_Up` | Scroll arriba |
| `ILoveYou` | Abrir enlace |
| `OK_Sign` | Scroll abajo |

Los mapeos y umbrales viven en `src/lib/config.js`.

## Estructura

```
src/
├── lib/        lógica pura (config, estabilizador, acciones, YouTube, dibujo)
├── workers/    MediaPipe en Web Worker
├── hooks/      useCamera, useGestureEngine, useYouTube, useTheme, useDesktopApp
├── components/ UI en React
└── styles/     tema claro/oscuro + estilos
```

## Gestos personalizados

```bash
uv pip install -r ../scripts/requirements-model-maker.txt
uv run python ../scripts/train_gesture_model.py --dataset dataset --epochs 10
```

Luego define `gestures.customModelUrl` en `src/lib/config.js`.

## Detección de la app de escritorio

El banner sondea `http://127.0.0.1:8765/health`. Si la app de escritorio está corriendo
(`Recognizer.exe --health-port 8765`), muestra "Abrir app"; si no, "Descargar app".
