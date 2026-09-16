/**
 * Recognizer Web — Estabilizador de gestos.
 *
 * Misma lógica que la app de escritorio: buffer de N frames, confirmación tras
 * M apariciones consecutivas, liberación tras M frames sin detectar el gesto.
 * Se expone como fábrica para que cada motor tenga su propio estado.
 */

import { CONFIG } from './config.js';

export function createStabilizer({ onConfirm, onRelease, onHeld } = {}) {
  const stabilizationFrames = CONFIG.gestures.stabilizationFrames;
  const releaseFrames = CONFIG.gestures.releaseFrames;
  const minConfidence = CONFIG.gestures.minConfidence;

  let buffer = [];
  let confirmed = null;
  let framesSinceLastSeen = 0;

  function selectTop(detections) {
    const filtered = detections.filter(
      (d) => d.confidence >= minConfidence && d.name && d.name !== 'None',
    );
    if (filtered.length === 0) return null;
    return filtered.reduce((best, curr) => (curr.confidence > best.confidence ? curr : best));
  }

  function allSame(arr) {
    return arr.every((v) => v === arr[0]);
  }

  function update(detections) {
    const top = selectTop(detections ?? []);

    if (top) {
      buffer.push(top.name);
      if (buffer.length > stabilizationFrames) buffer.shift();

      if (!confirmed) {
        if (buffer.length === stabilizationFrames && allSame(buffer)) {
          confirmed = top.name;
          framesSinceLastSeen = 0;
          onConfirm?.(confirmed, top.confidence, top.handedness);
        }
      } else {
        framesSinceLastSeen = 0;
        if (top.name === confirmed) {
          onHeld?.(confirmed, top.confidence, top.handedness);
        } else {
          buffer = [top.name];
        }
      }
    } else {
      buffer = [];
      if (confirmed) {
        framesSinceLastSeen += 1;
        if (framesSinceLastSeen >= releaseFrames) {
          const released = confirmed;
          confirmed = null;
          framesSinceLastSeen = 0;
          onRelease?.(released);
        }
      }
    }

    return confirmed;
  }

  function reset() {
    buffer = [];
    confirmed = null;
    framesSinceLastSeen = 0;
  }

  return { update, reset, getConfirmed: () => confirmed };
}
