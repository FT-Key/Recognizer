const STEPS = [
  {
    title: 'Da permiso a la cámara',
    text: 'Pulsa "Activar cámara". El navegador pedirá permiso una sola vez.',
  },
  {
    title: 'Muestra un gesto',
    text: 'Levanta la mano frente a la cámara. Los landmarks se dibujan en vivo sobre el video.',
  },
  {
    title: 'Mantén el gesto',
    text: 'El estabilizador confirma el gesto tras unos fotogramas para evitar falsos positivos.',
  },
  {
    title: 'Mira la acción',
    text: 'Se ejecuta al instante: play/pause, volumen, scroll o el siguiente video de tu lista.',
  },
];

export function HowItWorks() {
  return (
    <section className="section" id="como-funciona">
      <div className="container">
        <div className="section__head">
          <p className="eyebrow">Cómo funciona</p>
          <h2>De la mano a la acción en 4 pasos</h2>
        </div>

        <ol className="steps">
          {STEPS.map((step, index) => (
            <li className="step" key={step.title}>
              <span className="step__num" aria-hidden="true">
                {index + 1}
              </span>
              <h3>{step.title}</h3>
              <p>{step.text}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
