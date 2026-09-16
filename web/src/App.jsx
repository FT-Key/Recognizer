import { useCallback, useEffect, useRef, useState } from 'react';
import { Navbar } from './components/Navbar.jsx';
import { Footer } from './components/Footer.jsx';
import { ActionFeedback } from './components/ActionFeedback.jsx';
import { HomePage } from './pages/HomePage.jsx';
import { AboutPage } from './pages/AboutPage.jsx';
import { useCamera } from './hooks/useCamera.js';
import { useGestureEngine } from './hooks/useGestureEngine.js';
import { useYouTube } from './hooks/useYouTube.js';
import { useTheme } from './hooks/useTheme.js';
import { useDesktopApp } from './hooks/useDesktopApp.js';
import { usePathRoute } from './hooks/usePathRoute.js';
import { usePlaylist } from './hooks/usePlaylist.js';
import { CONFIG } from './lib/config.js';
import * as YT from './lib/youtube-controller.js';

const FEEDBACK_MS = 900;

function resolveHeaderStatus(engineStatus, engineError, cameraStatus, route) {
  if (route !== 'home') return engineError ? 'error' : 'idle';
  if (engineError) return 'error';
  if (engineStatus === 'ready') return 'ready';
  if (engineStatus === 'loading' || cameraStatus === 'requesting') return 'loading';
  return 'idle';
}

export default function App() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const youtubeContainerRef = useRef(null);
  const feedbackTimer = useRef(null);
  const [feedback, setFeedback] = useState(null);

  const { route, navigate } = usePathRoute();
  const { theme, toggle } = useTheme();
  const { available: desktopAvailable } = useDesktopApp();
  const camera = useCamera(videoRef);
  const playlist = usePlaylist();

  // El reproductor vive solo mientras estamos en Inicio; al salir se destruye.
  const youtube = useYouTube(
    youtubeContainerRef,
    playlist.current?.id ?? CONFIG.video.defaultVideoId,
    route === 'home',
  );

  const handleAction = useCallback(
    (mapping) => {
      if (mapping.action === 'ui' && mapping.command === 'toggle_theme') {
        toggle();
      }
      if (mapping.action === 'playlist' && mapping.command === 'next') {
        const video = playlist.next();
        if (video) YT.loadVideoById(video.id);
      }
      setFeedback({ label: mapping.label, icon: mapping.icon });
      if (feedbackTimer.current) clearTimeout(feedbackTimer.current);
      feedbackTimer.current = setTimeout(() => setFeedback(null), FEEDBACK_MS);
    },
    [toggle, playlist],
  );

  const engine = useGestureEngine({
    videoRef,
    canvasRef,
    enabled: camera.status === 'ready',
    onAction: handleAction,
  });

  // La cámara sigue activa al cambiar de página; al volver a Inicio se
  // reengancha el stream al <video> recién montado.
  const reattach = camera.reattach;
  useEffect(() => {
    if (route === 'home') reattach();
  }, [route, reattach]);

  // Al cambiar de página, subir al inicio (salvo en la carga inicial).
  const firstRoute = useRef(true);
  useEffect(() => {
    if (firstRoute.current) {
      firstRoute.current = false;
      return;
    }
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  }, [route]);

  const handleSelectDevice = useCallback(
    (id) => {
      camera.setDeviceId(id);
      camera.start(id);
    },
    [camera],
  );

  const handleAddVideo = useCallback(
    (url, title) => {
      const result = playlist.add(url, title);
      if (result.ok && result.video && playlist.videos.length === 0) {
        YT.loadVideoById(result.video.id);
      }
      return result;
    },
    [playlist],
  );

  const handleSelectVideo = useCallback(
    (position) => {
      playlist.select(position);
      const video = playlist.videos[position];
      if (video) YT.loadVideoById(video.id);
    },
    [playlist],
  );

  const headerStatus = resolveHeaderStatus(engine.status, engine.error, camera.status, route);

  return (
    <div className="app">
      <Navbar
        route={route}
        onNavigate={navigate}
        theme={theme}
        onToggleTheme={toggle}
        status={headerStatus}
        delegate={engine.delegate}
      />

      {engine.error && route === 'home' && (
        <div className="container">
          <div className="error-banner" role="alert">
            Error del reconocimiento: {engine.error}
          </div>
        </div>
      )}

      <main>
        {route === 'sobre-mi' ? (
          <AboutPage />
        ) : (
          <HomePage
            videoRef={videoRef}
            canvasRef={canvasRef}
            camera={camera}
            engine={engine}
            playlist={playlist}
            youtube={youtube}
            desktopAvailable={desktopAvailable}
            onSelectDevice={handleSelectDevice}
            onStartCamera={() => camera.start()}
            onAddVideo={handleAddVideo}
            onSelectVideo={handleSelectVideo}
            youtubeContainerRef={youtubeContainerRef}
          />
        )}
      </main>

      <Footer onNavigate={navigate} />
      <ActionFeedback feedback={feedback} />
    </div>
  );
}
