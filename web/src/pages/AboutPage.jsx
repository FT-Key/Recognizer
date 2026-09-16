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
    items: ['Node.js', 'Express', 'Nest.js', 'Laravel', 'REST APIs', 'GraphQL', 'WebSockets'],
  },
  {
    area: 'Bases de datos',
    items: ['MongoDB', 'MySQL', 'SQL Server', 'PostgreSQL', 'Neon', 'Redis'],
  },
  {
    area: 'Infra y DevOps',
    items: [
      'Docker',
      'Git / GitHub',
      'Vercel',
      'Netlify',
      'Render',
      'Oracle Cloud (VPS)',
      'Cloudflare R2',
    ],
  },
  {
    area: 'Pagos e integraciones',
    items: ['MercadoPago', 'Firebase', 'Nodemailer'],
  },
  {
    area: 'Lenguajes',
    items: ['JavaScript (ES6+)', 'TypeScript', 'Java', 'C++'],
  },
];

const PROCESS = [
  {
    step: '01',
    title: 'Entender',
    detail:
      'Escucho el problema, pregunto lo que falta y armo un plan corto antes de escribir la primera línea de código.',
  },
  {
    step: '02',
    title: 'Prototipar',
    detail:
      'Saco una versión mínima que funcione para validar la idea y detectar problemas temprano.',
  },
  {
    step: '03',
    title: 'Construir',
    detail:
      'Cuido la interfaz, el rendimiento y la legibilidad del código. Prefiero algo sólido a algo apurado.',
  },
  {
    step: '04',
    title: 'Desplegar',
    detail:
      'Lo pongo en producción (Vercel, Netlify, Render o mi VPS) y ajusto con feedback real.',
  },
];

const HOW_I_WORK = [
  {
    icon: 'book',
    title: 'Enseño',
    text: 'Ser tutor/mentor me obliga a explicar con claridad y a mantener el código legible. Documentar y simplificar es parte del trabajo.',
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
      <div className="about-photo__frame">
        {failed ? (
          <div className="about-photo__fallback">
            <div className="about-photo__icon">
              <Icon name="user" size={52} />
            </div>
            <p>Tu foto aquí (coloca el archivo en web/public/me.webp)</p>
          </div>
        ) : (
          <img
            className="about-photo__img"
            src={PHOTO_SRC}
            alt="Retrato de Franco Nicolás Toledo"
            onError={() => setFailed(true)}
          />
        )}
      </div>
      <figcaption className="about-photo__label">Franco Nicolás Toledo</figcaption>
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
              Desarrollador Web Full Stack &middot; Tutor/Mentor &middot; Estudiante de
              Ingeniería en Sistemas
            </p>
            <p>
              Soy Franco, desarrollador web full stack de Tucumán, Argentina. Me gusta construir
              productos completos: de la interfaz a la base de datos y el deploy.
            </p>
            <p>
              Trabajo con el stack MERN y también con Next.js, Nest.js y Laravel. Integro
              pasarelas de pago como MercadoPago, servicios como Firebase y Nodemailer, y
              despliego en Vercel, Netlify, Render o en un VPS propio en Oracle Cloud. También
              manejo Cloudflare R2, GraphQL y bases de datos SQL y NoSQL.
            </p>
            <p>
              Además de programar, doy clases: soy tutor/mentor en RollingCode School, donde
              acompaño a estudiantes con el stack MERN. Enseñar me obliga a explicar claro y a
              mantener el código legible, algo que después se nota en lo que construyo.
            </p>
            <p>
              Estudio Ingeniería en Sistemas de Información y soy autodidacta en programación.
              Recognizer nació como proyecto propio para explorar visión por computadora:
              reconocer gestos con la cámara y convertirlos en acciones reales.
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
              <article className="card card--tech" key={group.area}>
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
            <p className="eyebrow">Proceso</p>
            <h2>De la idea al deploy</h2>
            <p className="muted">
              Así encaro cada proyecto, del primer boceto al ajuste con usuarios reales.
            </p>
          </div>
          <ol className="timeline">
            {PROCESS.map((item) => (
              <li className="timeline__item" key={item.step}>
                <span className="timeline__when">{item.step}</span>
                <div className="timeline__what">
                  <h3>{item.title}</h3>
                  <p>{item.detail}</p>
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
