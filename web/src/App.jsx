import { useCallback, useRef, useState } from 'react';
import { Header } from './components/Header.jsx';
import { CameraPanel } from './components/CameraPanel.jsx';
import { VideoPanel } from './components/VideoPanel.jsx';
import { DownloadBanner } from './components/DownloadBanner.jsx';
import { ActionFeedback } from './components/ActionFeedback.jsx';
import { useCamera } from './hooks/useCamera.js';
import { useGestureEngine } from './hooks/useGestureEngine.js';
import { useYouTube } from './hooks/useYouTube.js';
import { useTheme } from './hooks/useTheme.js';
import { useDesktopApp } from './hooks/useDesktopApp.js';

const YOUTUBE_CONTAINER_ID = 'youtube-player';
const YOUTUBE_VIDEO_ID = 'dQw4w9WgXcQ';
const FEEDBACK_MS = 800;

function resolveHeaderStatus(engineStatus, engineError, cameraStatus) {
  if (engineError) return 'error';
  if (engineStatus === 'ready') return 'ready';
  if (engineStatus === 'loading' || cameraStatus === 'requesting') return 'loading';
  return 'idle';
}

export default function App() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const feedbackTimer = useRef(null);
  const [feedback, setFeedback] = useState(null);

  const { theme, toggle } = useTheme();
  const { available: desktopAvailable } = useDesktopApp();
  const camera = useCamera(videoRef);

  const handleAction = useCallback((mapping) => {
    setFeedback({ label: mapping.label, emoji: mapping.emoji });
    if (feedbackTimer.current) clearTimeout(feedbackTimer.current);
    feedbackTimer.current = setTimeout(() => setFeedback(null), FEEDBACK_MS);
  }, []);

  const engine = useGestureEngine({
    videoRef,
    canvasRef,
    enabled: camera.status === 'ready',
    onAction: handleAction,
  });

  const youtube = useYouTube(YOUTUBE_CONTAINER_ID, YOUTUBE_VIDEO_ID);

  const handleSelectDevice = useCallback(
    (id) => {
      camera.setDeviceId(id);
      camera.start(id);
    },
    [camera],
  );

  return (
    <div className="app">
      <Header
        status={resolveHeaderStatus(engine.status, engine.error, camera.status)}
        delegate={engine.delegate}
        theme={theme}
        onToggleTheme={toggle}
      />
      <main className="main">
        <CameraPanel
          videoRef={videoRef}
          canvasRef={canvasRef}
          devices={camera.devices}
          deviceId={camera.deviceId}
          onSelectDevice={handleSelectDevice}
          cameraStatus={camera.status}
          cameraError={camera.error}
          onRequestCamera={() => camera.start()}
          gesture={engine.gesture}
        />
        <VideoPanel
          containerId={YOUTUBE_CONTAINER_ID}
          fps={engine.fps}
          youtubeError={youtube.error}
        />
      </main>
      <DownloadBanner desktopAvailable={desktopAvailable} />
      <ActionFeedback feedback={feedback} />
    </div>
  );
}
