/**
 * useHashRoute — router mínimo por hash (#/ y #/sobre-mi).
 * Evita una dependencia de routing para solo dos páginas y funciona en
 * hosting estático (Vercel/GitHub Pages) sin rewrites.
 */

import { useCallback, useEffect, useState } from 'react';

const DEFAULT_ROUTE = 'home';

function readRoute() {
  const hash = window.location.hash.replace(/^#\/?/, '').trim();
  return hash || DEFAULT_ROUTE;
}

export function useHashRoute() {
  const [route, setRoute] = useState(readRoute);

  useEffect(() => {
    const onChange = () => setRoute(readRoute());
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);

  const navigate = useCallback((target) => {
    window.location.hash = `#/${target}`;
  }, []);

  return { route, navigate };
}
