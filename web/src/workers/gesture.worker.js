/**
 * Recognizer Web — Web Worker de reconocimiento de gestos.
 *
 * Worker CLASICO (sin imports ESM estaticos) para que funcione identico en
 * `vite dev` y en el build: MediaPipe se carga con import() dinamico desde el
 * CDN y su WASM con el importScripts() nativo del worker clasico.
 *
 * El hilo principal transfiere ImageBitmap por cada frame nuevo (con
 * backpressure: como mucho un frame en vuelo); el worker devuelve gestos,
 * landmarks y lateralidad.
 */

let FilesetResolver = null;
let GestureRecognizer = null;
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

async function ensureMediaPipe(moduleUrl) {
  if (GestureRecognizer) return;
  const mod = await import(/* @vite-ignore */ moduleUrl);
  FilesetResolver = mod.FilesetResolver;
  GestureRecognizer = mod.GestureRecognizer;
}

async function createRecognizer(options) {
  await ensureMediaPipe(options.moduleUrl);
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
    // Aun no listo: responder vacio para no bloquear el backpressure del cliente.
    message.bitmap?.close();
    self.postMessage({ type: 'result', gestures: [], landmarks: [], handednesses: [] });
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
