import * as YT from '../lib/youtube-controller.js';
import { GestureMap } from './GestureMap.jsx';

export function VideoPanel({ containerRef, fps, youtubeError, currentTitle }) {
  return (
    <section className="panel" aria-labelledby="video-title">
      <div className="panel__title">
        <span id="video-title">Reproductor</span>
        <span className="panel__title-dots" aria-hidden="true">
          &#x259A;&#x259A;
        </span>
      </div>
      <div className="panel__body">
        <div className="youtube-container">
          <div ref={containerRef} className="youtube-mount" />
        </div>

        <div className="meta-row">
          <span>FPS {fps || '--'}</span>
          <span>{youtubeError ? 'YouTube no disponible' : 'YouTube listo'}</span>
        </div>

        {currentTitle && (
          <p className="hint">
            Reproduciendo: <strong>{currentTitle}</strong>
          </p>
        )}

        <div className="panel__controls">
          <button type="button" className="btn btn--sm" onClick={() => YT.togglePlayPause()}>
            Play / Pause
          </button>
          <button type="button" className="btn btn--sm" onClick={() => YT.volumeDown()}>
            Vol -
          </button>
          <button type="button" className="btn btn--sm" onClick={() => YT.volumeUp()}>
            Vol +
          </button>
          <button type="button" className="btn btn--sm" onClick={() => YT.toggleMute()}>
            Mute
          </button>
        </div>

        <GestureMap />
      </div>
    </section>
  );
}
