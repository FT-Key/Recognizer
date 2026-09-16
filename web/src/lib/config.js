/**
 * Recognizer Web — Configuración.
 *
 * Valores equivalentes a config.yaml de la app de escritorio, pero con
 * acciones adaptadas al sandbox del navegador. La app web es independiente:
 * comparte el modelo de gestos, no la implementación de acciones.
 */

const MEDIAPIPE_VERSION = '0.10.18';
const MEDIAPIPE_CDN = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MEDIAPIPE_VERSION}`;

export const CONFIG = {
  camera: {
    facingMode: 'user',
    width: { ideal: 640 },
    height: { ideal: 480 },
  },

  gestures: {
    /** Módulo JS de MediaPipe (para el import dinámico del worker clásico). */
    moduleUrl: `${MEDIAPIPE_CDN}/vision_bundle.mjs`,
    /** WASM del runtime de MediaPipe. */
    wasmUrl: `${MEDIAPIPE_CDN}/wasm`,
    /** Modelo por defecto (canned gestures de Google). */
    modelUrl:
      'https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task',
    /**
     * Modelo personalizado entrenado con MediaPipe Model Maker.
     * Si se define, sustituye al modelo por defecto. Se puede apuntar a una
     * ruta local (p. ej. "models/custom_gesture_recognizer.task") o a una URL.
     * Genera el archivo con: uv run python scripts/train_gesture_model.py
     */
    customModelUrl: null,
    numHands: 2,
    minDetectionConfidence: 0.5,
    minPresenceConfidence: 0.5,
    minTrackingConfidence: 0.5,
    stabilizationFrames: 5,
    releaseFrames: 5,
    minConfidence: 0.5,
    /** 'GPU' con fallback automático a 'CPU' si falla. */
    delegate: 'GPU',
  },

  video: {
    /** Volumen inicial del reproductor (0-100). */
    initialVolume: 50,
    /** Video que se muestra al cargar y que se agrega si la playlist esta vacia. */
    defaultVideoId: 'dQw4w9WgXcQ',
    defaultVideoTitle: 'Rick Astley - Never Gonna Give You Up',
  },

  actions: {
    cooldownMs: 1000,
    mappings: {
      Open_Palm: {
        action: 'youtube',
        command: 'play_pause',
        label: 'Play / Pause',
        icon: 'handPaper',
      },
      Thumb_Up: {
        action: 'youtube',
        command: 'volume_up',
        label: 'Subir volumen',
        icon: 'thumbsUp',
        repeat: true,
        repeatIntervalMs: 400,
      },
      Thumb_Down: {
        action: 'youtube',
        command: 'volume_down',
        label: 'Bajar volumen',
        icon: 'thumbsDown',
        repeat: true,
        repeatIntervalMs: 400,
      },
      Closed_Fist: {
        action: 'navigation',
        command: 'scroll_down',
        label: 'Scroll abajo',
        icon: 'fist',
        repeat: true,
        repeatIntervalMs: 400,
      },
      Victory: {
        action: 'ui',
        command: 'toggle_theme',
        label: 'Cambiar tema',
        icon: 'peace',
      },
      Pointing_Up: {
        action: 'navigation',
        command: 'scroll_up',
        label: 'Scroll arriba',
        icon: 'pointer',
        repeat: true,
        repeatIntervalMs: 400,
      },
      ILoveYou: {
        action: 'playlist',
        command: 'next',
        label: 'Siguiente video',
        icon: 'spock',
      },
    },
  },

  ui: {
    landmarkColor: '#00E676',
    landmarkSize: 4,
    connectionColor: '#42A5F5',
    connectionWidth: 2,
    handednessColor: '#FFFFFF',
    mirrorVideo: true,
  },

  theme: {
    default: 'dark',
    storageKey: 'recognizer-theme',
  },

  /**
   * Detección de la app de escritorio: se sondea un endpoint local que la app
   * expone con `recognizer --health-port 8765`. Si responde, el banner ofrece
   * "Abrir app"; si no, ofrece la descarga.
   */
  desktop: {
    healthUrl: 'http://127.0.0.1:8765/health',
    /** Descarga de la app de escritorio (releases del repo). */
    downloadUrl: 'https://github.com/FT-Key/Recognizer/releases',
    probeTimeoutMs: 1200,
    probeIntervalMs: 15000,
  },
};

/** Modelo efectivo (custom si está definido, si no el de Google). */
export function resolveModelUrl() {
  return CONFIG.gestures.customModelUrl || CONFIG.gestures.modelUrl;
}

/** Mapeo gesto → metadatos para la UI. */
export function actionFor(gestureName) {
  return CONFIG.actions.mappings[gestureName] ?? null;
}
