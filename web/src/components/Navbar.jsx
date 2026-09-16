import { Icon } from '../lib/icons.jsx';
import { ROUTES } from '../hooks/usePathRoute.js';

const STATUS_TEXT = {
  idle: 'Inactivo',
  loading: 'Cargando',
  ready: 'Listo',
  error: 'Error',
};

export function Navbar({ route, onNavigate, theme, onToggleTheme, status, delegate }) {
  function go(event, target) {
    event.preventDefault();
    onNavigate(target);
  }

  return (
    <nav className="navbar">
      <div className="container navbar__inner">
        <a className="navbar__brand" href="/" onClick={(event) => go(event, 'home')}>
          <span className="navbar__brand-badge">
            <Icon name="handPaper" size={16} />
          </span>
          Recognizer
        </a>

        <ul className="navbar__links">
          {ROUTES.map((link) => (
            <li key={link.route}>
              <a
                className={`nav-link ${route === link.route ? 'nav-link--active' : ''}`}
                href={link.path}
                onClick={(event) => go(event, link.route)}
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
