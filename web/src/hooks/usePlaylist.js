/**
 * usePlaylist — gestiona la lista de videos (localStorage) y el video actual.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  extractYouTubeId,
  loadPlaylist,
  sanitizeTitle,
  savePlaylist,
} from '../lib/playlist.js';

export function usePlaylist() {
  const [videos, setVideos] = useState(() => loadPlaylist());
  const [index, setIndex] = useState(0);

  useEffect(() => {
    savePlaylist(videos);
  }, [videos]);

  // Si la lista se acorta, el índice no debe quedar fuera de rango.
  useEffect(() => {
    setIndex((current) => (videos.length === 0 ? 0 : Math.min(current, videos.length - 1)));
  }, [videos.length]);

  const add = useCallback(
    (input, title) => {
      const id = extractYouTubeId(input);
      if (!id) {
        return { ok: false, error: 'El enlace no es un video válido de YouTube.', video: null };
      }
      if (videos.some((video) => video.id === id)) {
        return { ok: false, error: 'Ese video ya está en la lista.', video: null };
      }
      const video = { id, title: sanitizeTitle(title) || `Video ${videos.length + 1}` };
      setVideos((current) => [...current, video]);
      return { ok: true, error: null, video };
    },
    [videos],
  );

  const remove = useCallback((target) => {
    setVideos((current) => current.filter((_, position) => position !== target));
  }, []);

  const select = useCallback(
    (target) => {
      if (target >= 0 && target < videos.length) setIndex(target);
    },
    [videos.length],
  );

  const next = useCallback(() => {
    if (videos.length === 0) return null;
    const nextIndex = (index + 1) % videos.length;
    setIndex(nextIndex);
    return videos[nextIndex];
  }, [videos, index]);

  return {
    videos,
    index,
    current: videos[index] ?? null,
    add,
    remove,
    select,
    next,
  };
}
