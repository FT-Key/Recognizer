import { Icon } from '../lib/icons.jsx';

const LINKS = [
  { route: 'home', label: 'Inicio', href: '#/' },
  { route: 'sobre-mi', label: 'Sobre mí', href: '#/sobre-mi' },
];

const STATUS_TEXT = {
  idle: 'Inactivo',
  loading: 'Cargando',
  ready: 'Listo',
  error: 'Error',
};

export function Navbar({ route, theme, onToggleTheme, status, delegate }) {
  return (
    <nav className="navbar">
      <div className="container navbar__inner">
        <a className="navbar__brand" href="#/">
          <span className="navbar__brand-badge">
            <Icon name="handPaper" size={16} />
          </span>
          Recognizer
        </a>

        <ul className="navbar__links">
          {LINKS.map((link) => (
            <li key={link.route}>
              <a
                className={`nav-link ${route === link.route ? 'nav-link--active' : ''}`}
                href={link.href}
                aria-current={route === link.route ? 'page' : undefined}
              >
                {link.label}
              </a>
            </li>
          ))}

          <li>
            <span className="status">
              <span className={`status-dot status-dot--${status}`} />
              {STATUS_TEXT[status] ?? status}
              {delegate ? ` \u00B7 ${delegate}` : ''}
            </span>
          </li>

          <li>
            <button
              type="button"
              className="btn btn--icon"
              onClick={onToggleTheme}
              aria-label="Cambiar tema claro/oscuro"
              title={theme === 'dark' ? 'Tema claro' : 'Tema oscuro'}
            >
              <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={18} />
            </button>
          </li>
        </ul>
      </div>
    </nav>
  );
}
