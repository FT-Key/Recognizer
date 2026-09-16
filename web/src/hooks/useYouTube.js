/**
 * useYouTube — carga la IFrame API y crea el reproductor embebido una sola vez.
 * El volumen inicial (50%) se fija al estar listo.
 */

import { useEffect, useRef, useState } from 'react';
import { CONFIG } from '../lib/config.js';
import { createPlayer, loadYouTubeAPI } from '../lib/youtube-controller.js';

export function useYouTube(containerId, initialVideoId) {
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(null);
  const initialIdRef = useRef(initialVideoId);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await loadYouTubeAPI();
        if (cancelled) return;
        await createPlayer(containerId, initialIdRef.current, {
          volume: CONFIG.video.initialVolume,
        });
        if (!cancelled) setReady(true);
      } catch (err) {
        if (!cancelled) setError(String(err?.message ?? err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [containerId]);

  return { ready, error };
}
