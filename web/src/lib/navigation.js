/**
 * Recognizer Web — Navegación del navegador.
 * Acciones permitidas por el sandbox: abrir pestañas y hacer scroll.
 */

const SCROLL_PIXELS = 300;

export function createNavigator({ cooldownMs = 500 } = {}) {
  let lastActionAt = 0;

  function canAct() {
    const now = Date.now();
    if (now - lastActionAt < cooldownMs) return false;
    lastActionAt = now;
    return true;
  }

  return {
    openNewTab(url) {
      if (!canAct()) return;
      window.open(url || 'https://www.google.com', '_blank', 'noopener');
    },
    scrollUp(pixels = SCROLL_PIXELS) {
      if (!canAct()) return;
      window.scrollBy({ top: -pixels, behavior: 'smooth' });
    },
    scrollDown(pixels = SCROLL_PIXELS) {
      if (!canAct()) return;
      window.scrollBy({ top: pixels, behavior: 'smooth' });
    },
  };
}
