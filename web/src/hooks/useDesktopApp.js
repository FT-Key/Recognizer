/**
 * useDesktopApp — detecta si la app de escritorio está corriendo.
 *
 * Sondea el endpoint de salud local (``recognizer --health-port 8765``). Si
 * responde, la app de escritorio está activa y el banner ofrece abrirla; si no,
 * ofrece la descarga. El sondeo se repite cada cierto intervalo.
 */

import { useEffect, useState } from 'react';
import { CONFIG } from '../lib/config.js';

export function useDesktopApp() {
  const [available, setAvailable] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer = null;

    async function probe() {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), CONFIG.desktop.probeTimeoutMs);
      try {
        const response = await fetch(CONFIG.desktop.healthUrl, {
          signal: controller.signal,
          cache: 'no-store',
        });
        if (!cancelled) setAvailable(response.ok);
      } catch {
        if (!cancelled) setAvailable(false);
      } finally {
        clearTimeout(timeout);
      }
    }

    probe();
    timer = setInterval(probe, CONFIG.desktop.probeIntervalMs);

    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, []);

  return { available };
}
