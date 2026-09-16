import { CONFIG } from '../lib/config.js';
import { Icon } from '../lib/icons.jsx';

export function GestureMap() {
  const entries = Object.entries(CONFIG.actions.mappings);

  return (
    <table className="gesture-map">
      <caption className="sr-only">Gestos disponibles y su acción en la web</caption>
      <thead>
        <tr>
          <th scope="col">Gesto</th>
          <th scope="col">Acción</th>
        </tr>
      </thead>
      <tbody>
        {entries.map(([name, mapping]) => (
          <tr key={name}>
            <td className="gesture-icon">
              <Icon name={mapping.icon} size={18} />
            </td>
            <td>
              <strong>{name}</strong> &rarr; {mapping.label}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
