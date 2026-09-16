import { Icon } from '../lib/icons.jsx';

const FEATURES = [
  {
    icon: 'lock',
    title: 'Privado por diseño',
    text: 'El reconocimiento corre en tu equipo con MediaPipe. La cámara nunca sale del navegador.',
  },
  {
    icon: 'bolt',
    title: 'Sin instalar nada',
    text: 'Entra a la página, da permiso a la cámara y empieza a usar gestos en segundos.',
  },
  {
    icon: 'clapper',
    title: 'Tu playlist',
    text: 'Agrega tus videos de YouTube y pásalos con el gesto ILoveYou. Quedan guardados en tu navegador.',
  },
  {
    icon: 'handPaper',
    title: '7 gestos listos',
    text: 'Play/pause, volumen, scroll, cambio de tema y salto de video, sin entrenar nada.',
  },
  {
    icon: 'desktop',
    title: 'También en escritorio',
    text: 'La app de escritorio controla mouse, teclado y volumen del sistema. Mismo motor, más poder.',
  },
  {
    icon: 'accessible',
    title: 'Accesible',
    text: 'Controles por teclado, foco visible y contraste cuidado. Pensado para usarse sin manos, pero usable con ellas.',
  },
];

export function Features() {
  return (
    <section className="section" id="caracteristicas">
      <div className="container">
        <div className="section__head">
          <p className="eyebrow">Características</p>
          <h2>Todo lo que hace Recognizer</h2>
          <p className="muted">
            Un puente entre tu cámara y tus acciones cotidianas, sin plugins ni extensiones.
          </p>
        </div>

        <div className="grid-3">
          {FEATURES.map((feature) => (
            <article className="card" key={feature.title}>
              <span className="card__icon">
                <Icon name={feature.icon} size={22} />
              </span>
              <h3>{feature.title}</h3>
              <p>{feature.text}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
