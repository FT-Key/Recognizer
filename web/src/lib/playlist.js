/**
 * Recognizer Web — Playlist de videos de YouTube.
 *
 * Guarda SOLO el id de 11 caracteres del video (nunca la URL ni HTML crudo) y
 * un título en texto plano, de modo que no haya inyección posible: React escapa
 * el título y el reproductor solo recibe ids validados.
 *
 * Acepta enlaces de escritorio y móviles: youtube.com/watch, youtu.be,
 * youtube.com/shorts, /embed, /live, /v y music.youtube.com.
 */

const STORAGE_KEY = 'recognizer-playlist';
const VIDEO_ID_PATTERN = /^[A-Za-z0-9_-]{11}$/;
const MAX_TITLE_LENGTH = 80;
const EMBED_SEGMENTS = new Set(['shorts', 'embed', 'live', 'v']);
const ALLOWED_HOSTS = new Set(['youtube.com', 'music.youtube.com', 'youtu.be', 'youtube-nocookie.com']);

/** Extrae el id de un enlace o id de YouTube; devuelve null si no es válido. */
export function extractYouTubeId(rawInput) {
  if (typeof rawInput !== 'string') return null;
  const input = rawInput.trim();
  if (!input) return null;
  if (VIDEO_ID_PATTERN.test(input)) return input;

  let url;
  try {
    url = new URL(input.includes('://') ? input : `https://${input}`);
  } catch {
    return null;
  }
  if (url.protocol !== 'https:' && url.protocol !== 'http:') return null;

  const host = url.hostname.toLowerCase().replace(/^www\./, '').replace(/^m\./, '');
  if (!ALLOWED_HOSTS.has(host)) return null;

  if (host === 'youtu.be') {
    const id = url.pathname.split('/').filter(Boolean)[0];
    return VIDEO_ID_PATTERN.test(id ?? '') ? id : null;
  }

  const queryId = url.searchParams.get('v');
  if (queryId && VIDEO_ID_PATTERN.test(queryId)) return queryId;

  const segments = url.pathname.split('/').filter(Boolean);
  const [first, second] = segments;
  if (first && EMBED_SEGMENTS.has(first) && second && VIDEO_ID_PATTERN.test(second)) {
    return second;
  }
  return null;
}

/** Limpia un título: quita caracteres de control y recorta a un máximo. */
export function sanitizeTitle(text) {
  if (typeof text !== 'string') return '';
  return text
    .replace(/[\u0000-\u001F\u007F]/g, '')
    .trim()
    .slice(0, MAX_TITLE_LENGTH);
}

/** Normaliza una lista cruda a elementos {id, title} válidos. */
export function normalizePlaylist(value) {
  if (!Array.isArray(value)) return [];
  const result = [];
  for (const item of value) {
    if (!item || typeof item !== 'object') continue;
    const id = typeof item.id === 'string' && VIDEO_ID_PATTERN.test(item.id) ? item.id : null;
    if (!id) continue;
    const title = sanitizeTitle(item.title) || `Video ${result.length + 1}`;
    result.push({ id, title });
  }
  return result;
}

/** Lee la playlist guardada en localStorage (lista vacía si falla). */
export function loadPlaylist() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return normalizePlaylist(JSON.parse(raw));
  } catch {
    return [];
  }
}

/** Persiste la playlist ya normalizada. */
export function savePlaylist(list) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(normalizePlaylist(list)));
  } catch {
    /* localStorage puede fallar en modo privado */
  }
}

/** URL canónica de reproducción a partir del id. */
export function watchUrl(id) {
  return `https://www.youtube.com/watch?v=${id}`;
}

/** Miniatura del video a partir del id. */
export function thumbnailUrl(id) {
  return `https://i.ytimg.com/vi/${id}/mqdefault.jpg`;
}
