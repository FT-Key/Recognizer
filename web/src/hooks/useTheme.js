/**
 * useTheme — tema claro/oscuro con persistencia en localStorage.
 */

import { useCallback, useEffect, useState } from 'react';
import { CONFIG } from '../lib/config.js';

function getInitialTheme() {
  try {
    const stored = localStorage.getItem(CONFIG.theme.storageKey);
    if (stored === 'light' || stored === 'dark') return stored;
  } catch {
    /* localStorage puede fallar en modo privado */
  }
  const prefersLight = window.matchMedia?.('(prefers-color-scheme: light)').matches;
  return prefersLight ? 'light' : CONFIG.theme.default;
}

export function useTheme() {
  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(CONFIG.theme.storageKey, theme);
    } catch {
      /* ignorar */
    }
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme((current) => (current === 'dark' ? 'light' : 'dark'));
  }, []);

  return { theme, toggle };
}
