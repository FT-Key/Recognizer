import { GestureMap } from './GestureMap.jsx';

export function VideoPanel({ containerId, fps, youtubeError }) {
  return (
    <section className="panel">
      <h2>Video</h2>
      <div className="youtube-container">
        <div id={containerId} />
      </div>
      <div className="meta-row">
        <span>FPS {fps || '--'}</span>
        <span>{youtubeError ? 'YouTube no disponible' : 'YouTube listo'}</span>
      </div>
      <GestureMap />
    </section>
  );
}
