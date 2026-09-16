/**
 * Recognizer Web — Navegación del navegador.
 * Acción permitida por el sandbox: hacer scroll en la propia página.
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
