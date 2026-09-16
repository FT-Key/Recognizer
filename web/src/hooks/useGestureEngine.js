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
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return undefined;

    let cancelled = false;
    const latest = { landmarks: [], handednesses: [], gesture: null, fps: 0 };

    const worker = new Worker(new URL('../workers/gesture.worker.js', import.meta.url), {
      type: 'module',
    });

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
        const value = { name, confidence, handedness };
        latest.gesture = value;
        setGesture(value);
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
        setDelegate(message.delegate);
        setStatus('ready');
        return;
      }
      if (message.type === 'error') {
        setError(message.message);
        return;
      }
      if (message.type === 'result') {
        latest.landmarks = message.landmarks;
        latest.handednesses = message.handednesses;
        stabilizer.update(message.gestures);
      }
    };

    setStatus('loading');
    worker.postMessage({
      type: 'init',
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

    const loop = (timestamp) => {
      if (cancelled) return;
      rafId = requestAnimationFrame(loop);
      if (video.readyState < 2) return;

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

      if (video.currentTime !== lastVideoTime) {
        lastVideoTime = video.currentTime;
        createImageBitmap(video)
          .then((bitmap) => worker.postMessage({ type: 'frame', bitmap, timestamp }, [bitmap]))
          .catch(() => {});
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
