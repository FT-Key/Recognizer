import { useState } from 'react';
import { thumbnailUrl, watchUrl } from '../lib/playlist.js';

export function PlaylistManager({ videos, index, onAdd, onRemove, onSelect }) {
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [message, setMessage] = useState(null);

  function handleSubmit(event) {
    event.preventDefault();
    const result = onAdd(url, title);
    if (result.ok) {
      setUrl('');
      setTitle('');
      setMessage({ kind: 'ok', text: 'Video agregado a tu lista.' });
    } else {
      setMessage({ kind: 'error', text: result.error });
    }
  }

  return (
    <section className="panel" aria-labelledby="playlist-title">
      <div className="panel__title">
        <span id="playlist-title">Mi playlist de YouTube</span>
        <span className="panel__title-dots" aria-hidden="true">
          &#x259A;&#x259A;
        </span>
      </div>
      <div className="panel__body">
        <p className="hint">
          Agrega enlaces de YouTube (escritorio o móvil). Se guardan solo en este navegador y
          el gesto <strong>ILoveYou</strong> pasa al siguiente video.
        </p>

        <form className="playlist__form" onSubmit={handleSubmit}>
          <div className="field">
            <label className="field__label" htmlFor="playlist-url">
              Enlace de YouTube
            </label>
            <input
              id="playlist-url"
              className="input"
              type="text"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://youtu.be/..."
              autoComplete="off"
            />
          </div>
          <div className="field">
            <label className="field__label" htmlFor="playlist-name">
              Título (opcional)
            </label>
            <input
              id="playlist-name"
              className="input"
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Mi video favorito"
              autoComplete="off"
            />
          </div>
          <button type="submit" className="btn btn--primary">
            Agregar
          </button>
        </form>

        {message && <p className={`hint hint--${message.kind}`}>{message.text}</p>}

        {videos.length === 0 ? (
          <p className="empty-state">
            Todavía no hay videos en la lista. Agrega el primero con el formulario de arriba.
          </p>
        ) : (
          <ul className="playlist__list">
            {videos.map((video, position) => (
              <li
                key={video.id}
                className={`playlist__item ${
                  position === index ? 'playlist__item--current' : ''
                }`}
              >
                <img
                  className="playlist__thumb"
                  src={thumbnailUrl(video.id)}
                  alt=""
                  loading="lazy"
                  width="72"
                  height="40"
                />
                <div className="playlist__info">
                  <div className="playlist__name" title={video.title}>
                    {video.title}
                  </div>
                  <div className="playlist__id">
                    {position === index ? 'En reproducción \u00B7 ' : ''}
                    <a href={watchUrl(video.id)} target="_blank" rel="noreferrer noopener">
                      {video.id}
                    </a>
                  </div>
                </div>
                <div className="playlist__actions">
                  <button
                    type="button"
                    className="btn btn--sm"
                    onClick={() => onSelect(position)}
                    disabled={position === index}
                  >
                    Ver
                  </button>
                  <button
                    type="button"
                    className="btn btn--sm"
                    onClick={() => onRemove(position)}
                    aria-label={`Quitar ${video.title}`}
                  >
                    Quitar
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
