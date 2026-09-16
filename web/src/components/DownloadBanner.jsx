import { CONFIG } from '../lib/config.js';

export function DownloadBanner({ desktopAvailable }) {
  const description = desktopAvailable
    ? 'La app de escritorio est\u00E1 corriendo en este equipo: controla mouse, teclado, volumen del sistema y aplicaciones.'
    : 'Descarga Recognizer para controlar tu PC completa: mouse, teclado, volumen del sistema y abrir aplicaciones.';

  return (
    <div className="banner">
      <div>
        <h3>&#x1F4BB; App de escritorio</h3>
        <p>{description}</p>
        {desktopAvailable && <span className="banner-badge">&#x25CF; Detectada en este equipo</span>}
      </div>
      <a className="banner-link" href={CONFIG.desktop.downloadUrl}>
        {desktopAvailable ? 'Abrir app' : 'Descargar app'}
      </a>
    </div>
  );
}
