const QUESTIONS = [
  {
    q: '¿Se sube mi video a algún servidor?',
    a: 'No. El reconocimiento corre con MediaPipe dentro de tu navegador. El video de la cámara nunca se envía a internet.',
  },
  {
    q: '¿Por qué no funciona con http://?',
    a: 'El navegador solo permite acceder a la cámara en contextos seguros: https:// o localhost. Vercel y GitHub Pages ya sirven por https.',
  },
  {
    q: '¿Qué gestos reconoce?',
    a: 'Siete gestos estándar: Open_Palm, Thumb_Up, Thumb_Down, Closed_Fist, Victory, Pointing_Up e ILoveYou. Cada uno tiene una acción asignada.',
  },
  {
    q: '¿Puedo usar mis propios videos?',
    a: 'Sí. Agrega enlaces de YouTube (de escritorio o móvil) en la playlist. Solo se aceptan enlaces de YouTube y se guardan en tu navegador.',
  },
  {
    q: '¿En qué se diferencia de la app de escritorio?',
    a: 'La web controla solo la pestaña (reproductor, scroll, tema) por el sandbox del navegador. La app de escritorio controla mouse, teclado, volumen del sistema y abre aplicaciones.',
  },
  {
    q: '¿Funciona en el celular?',
    a: 'La página es responsive y la cámara funciona en móviles modernos, aunque el rendimiento es mejor en una computadora.',
  },
];

export function Faq() {
  return (
    <section className="section" id="preguntas">
      <div className="container">
        <div className="section__head">
          <p className="eyebrow">Preguntas frecuentes</p>
          <h2>Dudas comunes</h2>
        </div>

        <div className="faq">
          {QUESTIONS.map((item) => (
            <details className="faq__item" key={item.q}>
              <summary>{item.q}</summary>
              <p>{item.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
