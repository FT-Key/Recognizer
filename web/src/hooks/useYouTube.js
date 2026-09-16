/**
 * useYouTube — carga la IFrame API y crea el reproductor embebido.
 */

import { useEffect, useState } from 'react';
import { createPlayer, loadYouTubeAPI } from '../lib/youtube-controller.js';

export function useYouTube(containerId, videoId) {
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await loadYouTubeAPI();
        if (cancelled) return;
        await createPlayer(containerId, videoId);
        if (!cancelled) setReady(true);
      } catch (err) {
        if (!cancelled) setError(String(err?.message ?? err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [containerId, videoId]);

  return { ready, error };
}
