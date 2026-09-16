const STATUS_TEXT = {
  idle: 'Inactivo',
  loading: 'Cargando modelo...',
  ready: 'Listo',
  error: 'Error',
};

const STATUS_CLASS = {
  ready: 'status-dot--ready',
  loading: 'status-dot--loading',
  error: 'status-dot--error',
};

export function Header({ status, delegate, theme, onToggleTheme }) {
  const text = STATUS_TEXT[status] ?? status;
  return (
    <header className="header">
      <h1>
        <span aria-hidden="true">&#x1F44B;</span> Recognizer Web
      </h1>
      <div className="header-actions">
        <div className="status">
          <span className={`status-dot ${STATUS_CLASS[status] ?? ''}`} />
          <span>
            {text}
            {delegate ? ` \u00B7 ${delegate}` : ''}
          </span>
        </div>
        <button
          type="button"
          className="icon-btn"
          onClick={onToggleTheme}
          title={theme === 'dark' ? 'Tema claro' : 'Tema oscuro'}
          aria-label="Cambiar tema"
        >
          {theme === 'dark' ? '\u2600\uFE0F' : '\uD83C\uDF19'}
        </button>
      </div>
    </header>
  );
}
