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
    /** WASM del runtime de MediaPipe (debe coincidir con la versión de npm). */
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

  actions: {
    cooldownMs: 1000,
    mappings: {
      Open_Palm: {
        action: 'youtube',
        command: 'play_pause',
        label: 'Play / Pause',
        emoji: '\u270B',
      },
      Thumb_Up: {
        action: 'youtube',
        command: 'volume_up',
        label: 'Subir volumen',
        emoji: '\uD83D\uDC4D',
      },
      Thumb_Down: {
        action: 'youtube',
        command: 'volume_down',
        label: 'Bajar volumen',
        emoji: '\uD83D\uDC4E',
      },
      Closed_Fist: {
        action: 'youtube',
        command: 'mute',
        label: 'Mute',
        emoji: '\u270A',
      },
      Victory: {
        action: 'navigation',
        command: 'new_tab',
        label: 'Nueva pesta\u00F1a',
        emoji: '\u270C\uFE0F',
      },
      Pointing_Up: {
        action: 'navigation',
        command: 'scroll_up',
        label: 'Scroll arriba',
        emoji: '\u261D\uFE0F',
      },
      ILoveYou: {
        action: 'navigation',
        command: 'open_url',
        url: 'https://www.youtube.com/watch?v=mlabBbn_fHI',
        label: 'Abrir enlace',
        emoji: '\uD83E\uDD1F',
      },
      OK_Sign: {
        action: 'navigation',
        command: 'scroll_down',
        label: 'Scroll abajo',
        emoji: '\uD83D\uDC4C',
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
    downloadUrl: '#descargar',
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
