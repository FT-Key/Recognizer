/**
 * usePathRoute — router mínimo con la History API (/ y /sobre-mi).
 *
 * Usa rutas reales para que recargar una página funcione (con el rewrite SPA de
 * vercel.json en producción y el fallback de Vite en dev/preview).
 */

import { useCallback, useEffect, useState } from 'react';

const DEFAULT_ROUTE = 'home';

export const ROUTES = [
  { route: 'home', path: '/', label: 'Inicio' },
  { route: 'sobre-mi', path: '/sobre-mi', label: 'Sobre mí' },
];

function readRoute() {
  const path = window.location.pathname.replace(/\/+$/, '').toLowerCase();
  const match = ROUTES.find((item) => item.path.toLowerCase() === path);
  return match ? match.route : DEFAULT_ROUTE;
}

export function pathFor(route) {
  return ROUTES.find((item) => item.route === route)?.path ?? '/';
}

export function usePathRoute() {
  const [route, setRoute] = useState(readRoute);

  useEffect(() => {
    const onPopState = () => setRoute(readRoute());
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  const navigate = useCallback((target) => {
    const path = pathFor(target);
    if (window.location.pathname !== path) {
      window.history.pushState({}, '', path);
    }
    setRoute(target);
  }, []);

  return { route, navigate };
}
