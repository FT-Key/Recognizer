/**
 * Recognizer Web — Controlador de YouTube.
 * Envuelve la YouTube IFrame API para controlar un video embebido.
 */

const DEFAULT_VIDEO_ID = 'dQw4w9WgXcQ';
const API_SCRIPT_SRC = 'https://www.youtube.com/iframe_api';
const VOLUME_STEP = 10;

let player = null;
let ready = false;
let apiPromise = null;

export function loadYouTubeAPI() {
  if (window.YT && window.YT.Player) return Promise.resolve();
  if (apiPromise) return apiPromise;

  apiPromise = new Promise((resolve) => {
    const previous = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      if (typeof previous === 'function') previous();
      resolve();
    };
    const tag = document.createElement('script');
    tag.src = API_SCRIPT_SRC;
    document.head.appendChild(tag);
  });
  return apiPromise;
}

export function createPlayer(containerId, videoId = DEFAULT_VIDEO_ID) {
  return new Promise((resolve) => {
    player = new window.YT.Player(containerId, {
      videoId,
      playerVars: { autoplay: 0, controls: 1, modestbranding: 1, rel: 0 },
      events: {
        onReady: () => {
          ready = true;
          resolve(player);
        },
      },
    });
  });
}

export function isReady() {
  return ready;
}

export function play() {
  if (ready) player.playVideo();
}

export function pause() {
  if (ready) player.pauseVideo();
}

export function togglePlayPause() {
  if (!ready) return;
  if (player.getPlayerState() === window.YT.PlayerState.PLAYING) pause();
  else play();
}

export function volumeUp(step = VOLUME_STEP) {
  if (ready) player.setVolume(Math.min(100, player.getVolume() + step));
}

export function volumeDown(step = VOLUME_STEP) {
  if (ready) player.setVolume(Math.max(0, player.getVolume() - step));
}

export function toggleMute() {
  if (!ready) return;
  if (player.isMuted()) player.unMute();
  else player.mute();
}

export function seekTo(seconds) {
  if (ready) player.seekTo(seconds, true);
}

export function loadVideoById(videoId) {
  if (ready) player.loadVideoById(videoId);
}
