import { actionFor } from '../lib/config.js';

export function GestureDisplay({ gesture }) {
  const mapping = gesture ? actionFor(gesture.name) : null;
  const percent = gesture ? Math.round((gesture.confidence ?? 0) * 100) : 0;
  const hint = mapping ? mapping.label : 'Muestra un gesto a la c\u00E1mara';

  return (
    <div className="gesture-display">
      <div className="gesture-emoji">{mapping?.emoji ?? '\u2014'}</div>
      <div className="gesture-info">
        <div className="label">{gesture?.name ?? 'Sin gesto'}</div>
        <div className="confidence">
          {hint}
          {gesture ? ` \u00B7 ${percent}%` : ''}
        </div>
        <div className="confidence-track">
          <div className="confidence-fill" style={{ width: `${percent}%` }} />
        </div>
      </div>
    </div>
  );
}
