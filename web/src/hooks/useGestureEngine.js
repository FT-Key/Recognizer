/**
 * useGestureEngine — orquesta worker, estabilizador, dispatcher y dibujo.
 *
 * El worker reconoce fuera del hilo de UI; aquí se estabilizan los gestos, se
 * disparan acciones y se dibuja el overlay en canvas a 60fps leyendo el último
 * resultado conocido (sin bloquear por la latencia del worker).
 */

import { useEffect, useRef, useState } from 'react';
import { CONFIG, resolveModelUrl } from '../lib/config.js';
import { createStabilizer } from '../lib/stabilizer.js';
import { createDispatcher } from '../lib/actions.js';
import { drawScene, syncCanvasSize } from '../lib/landmarks.js';

const FPS_WINDOW_MS = 1000;

export function useGestureEngine({ videoRef, canvasRef, enabled, onAction }) {
  const [status, setStatus] = useState('idle');
  const [delegate, setDelegate] = useState(null);
  const [error, setError] = useState(null);
  const [gesture, setGesture] = useState(null);
  const [fps, setFps] = useState(0);

  const onActionRef = useRef(onAction);
  onActionRef.current = onAction;

  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;
    const latest = { landmarks: [], handednesses: [], gesture: null, fps: 0 };

    // Worker clasico (sin imports ESM): funciona igual en dev y en produccion.
    const worker = new Worker(new URL('../workers/gesture.worker.js', import.meta.url));

    const dispatcher = createDispatcher({
      onAction: (mapping, meta) => onActionRef.current?.(mapping, meta),
    });

    const stabilizer = createStabilizer({
      onConfirm: (name, confidence, handedness) => {
        const value = { name, confidence, handedness };
        latest.gesture = value;
        setGesture(value);
        dispatcher.dispatch(name, confidence, handedness);
      },
      onHeld: (name, confidence, handedness) => {
        // Solo los gestos con repeticion (p. ej. volumen) se re-disparan al
        // mantenerse; el resto ya se ejecuto al confirmarse.
        const mapping = CONFIG.actions.mappings[name];
        if (!mapping?.repeat) return;
        latest.gesture = { name, confidence, handedness };
        dispatcher.dispatch(name, confidence, handedness);
      },
      onRelease: () => {
        latest.gesture = null;
        setGesture(null);
      },
    });

    worker.onmessage = (event) => {
      const message = event.data;
      if (message.type === 'ready') {
        workerReady = true;
        setDelegate(message.delegate);
        setStatus('ready');
        return;
      }
      if (message.type === 'error') {
        frameInFlight = false;
        console.error('[gesture.worker]', message.message);
        setError(message.message);
        return;
      }
      if (message.type === 'result') {
        frameInFlight = false;
        latest.landmarks = message.landmarks;
        latest.handednesses = message.handednesses;
        stabilizer.update(message.gestures);
      }
    };

    setStatus('loading');
    worker.postMessage({
      type: 'init',
      moduleUrl: CONFIG.gestures.moduleUrl,
      wasmUrl: CONFIG.gestures.wasmUrl,
      modelUrl: resolveModelUrl(),
      delegate: CONFIG.gestures.delegate,
      numHands: CONFIG.gestures.numHands,
      minDetectionConfidence: CONFIG.gestures.minDetectionConfidence,
      minPresenceConfidence: CONFIG.gestures.minPresenceConfidence,
      minTrackingConfidence: CONFIG.gestures.minTrackingConfidence,
    });

    let rafId = null;
    let lastVideoTime = -1;
    let lastTs = 0;
    let frameCount = 0;
    let fpsAccum = 0;
    // No enviar frames hasta que el modelo este cargado: si llegan durante la
    // inicializacion el worker los descarta y, con backpressure, la cola se
    // quedaria bloqueada esperando una respuesta que nunca llega.
    let workerReady = false;
    // Backpressure: como mucho un frame en vuelo hacia el worker. Sin esto, si
    // la inferencia va mas lenta que la camara la cola crece sin limite y el
    // overlay se retrasa segundos respecto a la mano real.
    let frameInFlight = false;

    const loop = (timestamp) => {
      if (cancelled) return;
      rafId = requestAnimationFrame(loop);

      // Los refs se leen en cada frame: al cambiar de pagina el <video>/<canvas>
      // se desmontan y el worker sigue vivo, listo para cuando vuelvan.
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || video.readyState < 2) return;

      if (lastTs) {
        frameCount += 1;
        fpsAccum += timestamp - lastTs;
        if (fpsAccum >= FPS_WINDOW_MS) {
          const value = Math.round((frameCount * FPS_WINDOW_MS) / fpsAccum);
          latest.fps = value;
          setFps(value);
          frameCount = 0;
          fpsAccum = 0;
        }
      }
      lastTs = timestamp;

      if (workerReady && !frameInFlight && video.currentTime !== lastVideoTime) {
        lastVideoTime = video.currentTime;
        frameInFlight = true;
        createImageBitmap(video)
          .then((bitmap) => worker.postMessage({ type: 'frame', bitmap, timestamp }, [bitmap]))
          .catch(() => {
            frameInFlight = false;
          });
      }

      const { ctx, width, height } = syncCanvasSize(canvas, video);
      drawScene(ctx, {
        landmarks: latest.landmarks,
        handednesses: latest.handednesses,
        gesture: latest.gesture,
        fps: latest.fps,
        width,
        height,
        colors: CONFIG.ui,
        mirror: CONFIG.ui.mirrorVideo,
      });
    };

    rafId = requestAnimationFrame(loop);

    return () => {
      cancelled = true;
      if (rafId) cancelAnimationFrame(rafId);
      worker.postMessage({ type: 'close' });
      worker.terminate();
    };
  }, [enabled, videoRef, canvasRef]);

  return { status, delegate, error, gesture, fps };
}
