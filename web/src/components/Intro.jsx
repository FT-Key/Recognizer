import { Icon } from '../lib/icons.jsx';

const GESTURES = [
  { name: 'Open_Palm', icon: 'handPaper' },
  { name: 'Thumb_Up', icon: 'thumbsUp' },
  { name: 'Thumb_Down', icon: 'thumbsDown' },
  { name: 'Closed_Fist', icon: 'fist' },
  { name: 'Victory', icon: 'peace' },
  { name: 'Pointing_Up', icon: 'pointer' },
  { name: 'ILoveYou', icon: 'spock' },
];

export function Intro({ onStart }) {
  return (
    <section className="intro" id="intro">
      <div className="container">
        <div className="intro__panel">
          <p className="eyebrow">Visión por computadora &middot; sin instalar nada</p>
          <h1 className="intro__title">
            Controla tu PC con <span>gestos de mano</span>
          </h1>
          <p className="intro__text">
            Recognizer usa tu cámara para reconocer gestos y ejecutar acciones: reproducir y
            cambiar de video, subir el volumen, scrollear o cambiar el tema. Todo el
            procesamiento ocurre en tu navegador; tu video nunca se sube a un servidor.
          </p>
          <div className="intro__actions">
            <button type="button" className="btn btn--primary" onClick={onStart}>
              Probar ahora
            </button>
            <a className="btn" href="#como-funciona">
              Cómo funciona
            </a>
          </div>
          <ul className="marquee" aria-hidden="true">
            {GESTURES.map((item) => (
              <li key={item.name}>
                <Icon name={item.icon} size={16} /> {item.name}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
