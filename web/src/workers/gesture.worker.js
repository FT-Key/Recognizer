/**
 * Recognizer Web — Web Worker de reconocimiento de gestos.
 *
 * Corre MediaPipe Tasks Vision fuera del hilo de UI para no bloquear el render.
 * El hilo principal transfiere ImageBitmap por cada frame nuevo; el worker
 * devuelve gestos, landmarks y lateralidad.
 */

import { FilesetResolver, GestureRecognizer } from '@mediapipe/tasks-vision';

/**
 * MediaPipe carga su WASM con `importScripts()`, que en un worker de modulo
 * existe pero lanza ("Module scripts don't support importScripts()"). Lo
 * sustituimos por una carga sincrona via XHR + eval, que es lo que hace
 * `importScripts` internamente, para que funcione en dev y en produccion.
 */
function installImportScriptsShim() {
  if (typeof self.importScripts !== 'function') return;

  self.importScripts = (...urls) => {
    for (const url of urls) {
      const xhr = new XMLHttpRequest();
      xhr.open('GET', url, false);
      xhr.send(null);
      if (xhr.status < 200 || xhr.status >= 300) {
        throw new Error(`No se pudo cargar ${url} (${xhr.status})`);
      }
      (0, eval)(xhr.responseText);
    }
  };
}

installImportScriptsShim();

let recognizer = null;
let lastTimestamp = -1;
let activeDelegate = null;

function parseResult(result) {
  if (!result || !result.gestures) {
    return { gestures: [], landmarks: [], handednesses: [] };
  }

  const gestures = result.gestures.map((categories, index) => {
    const top = categories[0] ?? { categoryName: 'None', score: 0 };
    return {
      name: top.categoryName,
      confidence: top.score,
      handedness: result.handednesses?.[index]?.[0]?.categoryName ?? 'Unknown',
    };
  });

  const landmarks = (result.landmarks ?? []).map((hand) =>
    hand.map((point) => ({ x: point.x, y: point.y, z: point.z })),
  );

  const handednesses = (result.handednesses ?? []).map((hand) =>
    hand.map((category) => ({ categoryName: category.categoryName, score: category.score })),
  );

  return { gestures, landmarks, handednesses };
}

async function createRecognizer(options) {
  const vision = await FilesetResolver.forVisionTasks(options.wasmUrl);
  const buildOptions = (delegate) => ({
    baseOptions: { modelAssetPath: options.modelUrl, delegate },
    runningMode: 'VIDEO',
    numHands: options.numHands,
    minHandDetectionConfidence: options.minDetectionConfidence,
    minHandPresenceConfidence: options.minPresenceConfidence,
    minTrackingConfidence: options.minTrackingConfidence,
  });

  try {
    return { instance: await GestureRecognizer.createFromOptions(vision, buildOptions(options.delegate)), delegate: options.delegate };
  } catch (error) {
    if (options.delegate === 'CPU') throw error;
    return {
      instance: await GestureRecognizer.createFromOptions(vision, buildOptions('CPU')),
      delegate: 'CPU',
    };
  }
}

async function handleInit(message) {
  const created = await createRecognizer(message);
  recognizer = created.instance;
  activeDelegate = created.delegate;
  self.postMessage({ type: 'ready', delegate: activeDelegate });
}

function handleFrame(message) {
  if (!recognizer) {
    message.bitmap?.close();
    return;
  }
  const timestamp = Math.max(message.timestamp, lastTimestamp + 1);
  lastTimestamp = timestamp;
  const result = recognizer.recognizeForVideo(message.bitmap, timestamp);
  const parsed = parseResult(result);
  self.postMessage({ type: 'result', ...parsed });
  message.bitmap.close();
}

self.onmessage = async (event) => {
  const message = event.data;
  try {
    if (message.type === 'init') {
      await handleInit(message);
    } else if (message.type === 'frame') {
      handleFrame(message);
    } else if (message.type === 'close') {
      recognizer?.close();
      recognizer = null;
      self.close();
    }
  } catch (error) {
    message.bitmap?.close?.();
    self.postMessage({ type: 'error', message: String(error?.message ?? error) });
  }
};
