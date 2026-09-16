import { CameraPanel } from '../components/CameraPanel.jsx';
import { VideoPanel } from '../components/VideoPanel.jsx';
import { Intro } from '../components/Intro.jsx';
import { PlaylistManager } from '../components/PlaylistManager.jsx';
import { Features } from '../components/Features.jsx';
import { HowItWorks } from '../components/HowItWorks.jsx';
import { Faq } from '../components/Faq.jsx';
import { DownloadBanner } from '../components/DownloadBanner.jsx';

export function HomePage({
  videoRef,
  canvasRef,
  camera,
  engine,
  playlist,
  youtube,
  desktopAvailable,
  onSelectDevice,
  onStartCamera,
  onAddVideo,
  onSelectVideo,
  youtubeContainerId,
}) {
  return (
    <>
      <section className="section section--tight" id="demo">
        <div className="container">
          <div className="section__head">
            <p className="eyebrow">Demo en vivo</p>
            <h2>Pruébalo con tu cámara</h2>
            <p className="muted">
              Activa la cámara y muestra un gesto. Verás los puntos de tu mano en tiempo real
              y el gesto confirmado con su acción.
            </p>
          </div>

          <div className="workbench">
            <CameraPanel
              videoRef={videoRef}
              canvasRef={canvasRef}
              devices={camera.devices}
              deviceId={camera.deviceId}
              onSelectDevice={onSelectDevice}
              cameraStatus={camera.status}
              cameraError={camera.error}
              onRequestCamera={onStartCamera}
              gesture={engine.gesture}
            />
            <VideoPanel
              containerId={youtubeContainerId}
              fps={engine.fps}
              youtubeError={youtube.error}
              currentTitle={playlist.current?.title}
            />
          </div>
        </div>
      </section>

      <Intro onStart={onStartCamera} />

      <section className="section section--tight" id="playlist">
        <div className="container">
          <PlaylistManager
            videos={playlist.videos}
            index={playlist.index}
            onAdd={onAddVideo}
            onRemove={playlist.remove}
            onSelect={onSelectVideo}
          />
        </div>
      </section>

      <Features />
      <HowItWorks />
      <Faq />

      <section className="section section--tight">
        <div className="container">
          <DownloadBanner desktopAvailable={desktopAvailable} />
        </div>
      </section>
    </>
  );
}
