import { useState } from 'react';
import { Icon } from '../lib/icons.jsx';

const PORTFOLIO_URL = 'https://ftkey-portfolio.netlify.app/';
const GITHUB_URL = 'https://github.com/FT-Key';
const LINKEDIN_URL = 'https://www.linkedin.com/in/ftkey/';
const EMAIL = 'fr4nc0t2@gmail.com';
const PHOTO_SRC = '/me.webp';

const SKILL_GROUPS = [
  {
    area: 'Frontend',
    items: ['React', 'Next.js', 'TailwindCSS', 'Ant Design', 'Bootstrap', 'HTML5', 'CSS3'],
  },
  {
    area: 'Backend',
    items: ['Node.js', 'Express', 'Nest.js', 'Laravel', 'REST APIs', 'WebSockets'],
  },
  {
    area: 'Bases de datos',
    items: ['MongoDB', 'MySQL', 'PostgreSQL', 'Redis', 'Firebase'],
  },
  {
    area: 'Lenguajes',
    items: ['JavaScript (ES6+)', 'TypeScript', 'Java', 'C++', 'Python'],
  },
  {
    area: 'Herramientas',
    items: ['Git / GitHub', 'Docker', 'Vercel', 'Render', 'Netlify', 'Scrum'],
  },
];

const TIMELINE = [
  {
    when: '2025 – Actualidad',
    what: 'Tutor de programación',
    where: 'RollingCode School',
    detail:
      'Acompaño a estudiantes en el stack MERN y en buenas prácticas de desarrollo web y trabajo colaborativo.',
  },
  {
    when: '2025',
    what: 'Desarrollador Web',
    where: 'RollingCode School',
    detail:
      'Proyectos internos con MongoDB, Next.js, React, Node.js, Express y TailwindCSS; integración de Firebase, Nodemailer y pagos, y despliegues en Vercel, Netlify y Render.',
  },
  {
    when: '2024 – Actualidad',
    what: 'Ingeniería en Sistemas de Información (4.º año)',
    where: 'Universidad Tecnológica Nacional',
    detail: 'Carrera de grado en curso, combinada con formación autodidacta en programación.',
  },
  {
    when: '2025 – 2026',
    what: 'Programación asistida por IA',
    where: 'RollingCode School',
    detail: 'Formación enfocada en desarrollo con inteligencia artificial y automatización.',
  },
  {
    when: '2024',
    what: 'Desarrollo Web Full Stack (MERN)',
    where: 'RollingCode School',
    detail: 'MongoDB, Express, React y Node.js, con foco en proyectos reales.',
  },
  {
    when: '2016 – 2019',
    what: 'Pasantía en desarrollo de sistemas de escritorio',
    where: 'Atilio Marola SRL',
    detail: 'Primeros pasos profesionales desarrollando un sistema de escritorio.',
  },
];

const HOW_I_WORK = [
  {
    icon: 'book',
    title: 'Enseño',
    text: 'Ser tutor me obliga a explicar con claridad y a mantener el código legible. Documentar y simplificar es parte del trabajo.',
  },
  {
    icon: 'wrench',
    title: 'Construyo',
    text: 'Prefiero entregar algo que funcione y mejorarlo con feedback. Del prototipo al deploy en Vercel, Netlify o Render.',
  },
  {
    icon: 'rocket',
    title: 'Aprendo',
    text: 'Soy autodidacta. Estudio Ingeniería en Sistemas y complemento con cursos y proyectos propios, como este Recognizer.',
  },
];

const PROJECTS = [
  { name: 'Hexagonizer', kind: 'Paquete NPM' },
  { name: 'Git-accounts', kind: 'Paquete NPM' },
  { name: 'Ravello Turismo', kind: 'Sitio con SEO' },
  { name: 'Ant Form Builder', kind: 'Formularios con IA' },
  { name: 'Cener Gym', kind: 'Sistema + landing' },
  { name: 'Remote Code', kind: 'IDE en la nube' },
];

function AboutPhoto() {
  const [failed, setFailed] = useState(false);

  return (
    <figure className="about-photo">
      {failed ? (
        <div>
          <div className="about-photo__icon">
            <Icon name="user" size={52} />
          </div>
          <p>Tu foto aquí (coloca el archivo en web/public/me.webp)</p>
        </div>
      ) : (
        <img
          src={PHOTO_SRC}
          alt="Retrato de Franco Nicolás Toledo"
          onError={() => setFailed(true)}
        />
      )}
    </figure>
  );
}

export function AboutPage() {
  return (
    <>
      <section className="section">
        <div className="container about-hero">
          <AboutPhoto />

          <div className="about-bio">
            <p className="eyebrow">Sobre mí</p>
            <h1>Franco Nicolás Toledo</h1>
            <p className="about-role">
              Desarrollador Web Full Stack &middot; Estudiante de Ingeniería en Sistemas
            </p>
            <p>
              Soy desarrollador web full stack y tutor de programación en Tucumán, Argentina.
              Trabajé en el desarrollo de proyectos internos con el stack MERN y hoy combino el
              trabajo independiente y freelance con mis estudios de Ingeniería en Sistemas de
              Información.
            </p>
            <p>
              Me apasiona la tecnología y el aprendizaje continuo: arranqué como autodidacta y
              sigo formándome en Python y en desarrollo con inteligencia artificial. Disfruto
              tanto construir productos como explicar cómo funcionan.
            </p>
            <p>
              Recognizer nació como un proyecto propio para explorar visión por computadora:
              reconocer gestos con la cámara y convertirlos en acciones reales, en el navegador
              y en el escritorio.
            </p>

            <ul className="contact-list">
              <li>
                <a className="btn btn--sm" href={`mailto:${EMAIL}`}>
                  {EMAIL}
                </a>
              </li>
              <li>
                <a
                  className="btn btn--sm"
                  href={GITHUB_URL}
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  GitHub /FT-Key
                </a>
              </li>
              <li>
                <a
                  className="btn btn--sm"
                  href={LINKEDIN_URL}
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  LinkedIn /in/ftkey
                </a>
              </li>
            </ul>
          </div>
        </div>
      </section>

      <section className="section section--tight">
        <div className="container">
          <div className="section__head">
            <p className="eyebrow">Cómo trabajo</p>
            <h2>Tres cosas que me definen</h2>
          </div>
          <div className="grid-3">
            {HOW_I_WORK.map((item) => (
              <article className="card" key={item.title}>
                <span className="card__icon">
                  <Icon name={item.icon} size={22} />
                </span>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section section--tight">
        <div className="container">
          <div className="section__head">
            <p className="eyebrow">Habilidades</p>
            <h2>Con qué trabajo</h2>
          </div>
          <div className="grid-2">
            {SKILL_GROUPS.map((group) => (
              <article className="card" key={group.area}>
                <h3>{group.area}</h3>
                <ul className="tag-list">
                  {group.items.map((item) => (
                    <li className="tag" key={item}>
                      {item}
                    </li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section section--tight">
        <div className="container">
          <div className="section__head">
            <p className="eyebrow">Trayectoria</p>
            <h2>Experiencia y formación</h2>
          </div>
          <ol className="timeline">
            {TIMELINE.map((entry) => (
              <li className="timeline__item" key={`${entry.when}-${entry.what}`}>
                <span className="timeline__when">{entry.when}</span>
                <div className="timeline__what">
                  <h3>{entry.what}</h3>
                  <p className="muted">{entry.where}</p>
                  <p>{entry.detail}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="section section--tight">
        <div className="container">
          <div className="section__head">
            <p className="eyebrow">Proyectos</p>
            <h2>Algunas cosas que construí</h2>
          </div>
          <div className="grid-3">
            {PROJECTS.map((project) => (
              <article className="card" key={project.name}>
                <h3>{project.name}</h3>
                <p className="muted">{project.kind}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section section--tight">
        <div className="container">
          <div className="banner">
            <div>
              <h3>¿Querés ver más?</h3>
              <p>En mi portfolio están los detalles de cada proyecto, stack y demos en vivo.</p>
            </div>
            <a
              className="btn btn--primary"
              href={PORTFOLIO_URL}
              target="_blank"
              rel="noreferrer noopener"
            >
              Ver portfolio
            </a>
          </div>
        </div>
      </section>
    </>
  );
}
