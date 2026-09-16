/**
 * useYouTube — crea el reproductor cuando la página está activa y lo destruye al
 * salir, para que el iframe no quede huérfano (pantalla negra al volver).
 *
 * El reproductor se monta en un div creado a mano dentro del contenedor: YouTube
 * reemplaza ese div por su iframe, así el árbol de React no guarda una referencia
 * obsoleta del nodo reemplazado.
 */

import { useEffect, useRef, useState } from 'react';
import { CONFIG } from '../lib/config.js';
import * as YT from '../lib/youtube-controller.js';

export function useYouTube(containerRef, videoId, enabled) {
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(null);
  const videoIdRef = useRef(videoId);
  videoIdRef.current = videoId;

  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;
    setReady(false);

    (async () => {
      try {
        await YT.loadYouTubeAPI();
        if (cancelled || !containerRef.current) return;

        const mount = document.createElement('div');
        containerRef.current.appendChild(mount);

        await YT.createPlayer(mount, videoIdRef.current, {
          volume: CONFIG.video.initialVolume,
        });
        if (!cancelled) setReady(true);
      } catch (err) {
        if (!cancelled) setError(String(err?.message ?? err));
      }
    })();

    return () => {
      cancelled = true;
      YT.destroyPlayer();
      setReady(false);
    };
  }, [containerRef, enabled]);

  return { ready, error };
}
