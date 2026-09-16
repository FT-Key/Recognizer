const PORTFOLIO_URL = 'https://ftkey-portfolio.netlify.app/';
const GITHUB_URL = 'https://github.com/FT-Key';
const LINKEDIN_URL = 'https://www.linkedin.com/in/ftkey/';

export function Footer({ onNavigate }) {
  const year = new Date().getFullYear();

  function go(event, target) {
    event.preventDefault();
    onNavigate(target);
  }

  return (
    <footer className="footer">
      <div className="container footer__inner">
        <p>
          Recognizer &mdash; visión por computadora en el navegador. &copy; {year} Franco
          Nicolás Toledo.
        </p>
        <ul className="footer__links">
          <li>
            <a href="/" onClick={(event) => go(event, 'home')}>
              Inicio
            </a>
          </li>
          <li>
            <a href="/sobre-mi" onClick={(event) => go(event, 'sobre-mi')}>
              Sobre mí
            </a>
          </li>
          <li>
            <a href={PORTFOLIO_URL} target="_blank" rel="noreferrer noopener">
              Portfolio
            </a>
          </li>
          <li>
            <a href={GITHUB_URL} target="_blank" rel="noreferrer noopener">
              GitHub
            </a>
          </li>
          <li>
            <a href={LINKEDIN_URL} target="_blank" rel="noreferrer noopener">
              LinkedIn
            </a>
          </li>
        </ul>
      </div>
    </footer>
  );
}
