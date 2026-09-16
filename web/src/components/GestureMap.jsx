import { CONFIG } from '../lib/config.js';

export function GestureMap() {
  const entries = Object.entries(CONFIG.actions.mappings);

  return (
    <table className="gesture-map">
      <thead>
        <tr>
          <th>Gesto</th>
          <th>Acción</th>
        </tr>
      </thead>
      <tbody>
        {entries.map(([name, mapping]) => (
          <tr key={name}>
            <td className="emoji">{mapping.emoji}</td>
            <td>
              {name} → {mapping.label}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
