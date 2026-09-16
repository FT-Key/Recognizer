/**
 * Recognizer Web — Estabilizador de gestos.
 *
 * Misma lógica que la app de escritorio: un gesto se confirma tras N frames
 * consecutivos y se libera tras M frames sin verlo. Un gesto distinto puede
 * reemplazar al confirmado cuando alcanza N frames (publica la liberación del
 * anterior y la detección del nuevo).
 *
 * Se expone como fábrica para que cada motor tenga su propio estado.
 */

import { CONFIG } from './config.js';

export function createStabilizer({ onConfirm, onRelease, onHeld } = {}) {
  const stabilizationFrames = CONFIG.gestures.stabilizationFrames;
  const releaseFrames = CONFIG.gestures.releaseFrames;
  const minConfidence = CONFIG.gestures.minConfidence;

  let confirmed = null;
  let candidate = null;
  let candidateFrames = 0;
  let missingFrames = 0;

  function selectTop(detections) {
    const filtered = detections.filter(
      (d) => d.confidence >= minConfidence && d.name && d.name !== 'None',
    );
    if (filtered.length === 0) return null;
    return filtered.reduce((best, curr) => (curr.confidence > best.confidence ? curr : best));
  }

  function update(detections) {
    const top = selectTop(detections ?? []);

    // 1) El gesto confirmado sigue presente: se mantiene y se emite "held".
    if (top && confirmed === top.name) {
      candidate = null;
      candidateFrames = 0;
      missingFrames = 0;
      onHeld?.(confirmed, top.confidence, top.handedness);
      return confirmed;
    }

    // 2) Hay una observacion: acumular candidato y confirmarlo al llegar a N.
    if (top) {
      if (candidate === top.name) {
        candidateFrames += 1;
      } else {
        candidate = top.name;
        candidateFrames = 1;
      }

      if (candidateFrames >= stabilizationFrames) {
        const previous = confirmed;
        if (previous !== null && previous !== top.name) {
          onRelease?.(previous);
        }
        confirmed = top.name;
        candidate = null;
        candidateFrames = 0;
        missingFrames = 0;
        onConfirm?.(confirmed, top.confidence, top.handedness);
        return confirmed;
      }
    } else {
      candidate = null;
      candidateFrames = 0;
    }

    // 3) El gesto confirmado no se observa (o lo desplaza un candidato):
    //    contar ausencias y liberarlo al llegar a M.
    if (confirmed !== null) {
      missingFrames += 1;
      if (missingFrames >= releaseFrames) {
        const released = confirmed;
        confirmed = null;
        missingFrames = 0;
        onRelease?.(released);
      }
    }

    return confirmed;
  }

  function reset() {
    confirmed = null;
    candidate = null;
    candidateFrames = 0;
    missingFrames = 0;
  }

  return { update, reset, getConfirmed: () => confirmed };
}
