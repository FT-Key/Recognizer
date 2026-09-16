/**
 * Recognizer Web — Registro de iconos (Font Awesome 6 vía react-icons).
 *
 * Centraliza los iconos para que toda la UI use el mismo set y herede el color
 * del tema (`currentColor`), en vez de emojis con colores fijos.
 */

import {
  FaBolt,
  FaBookOpen,
  FaClapperboard,
  FaDesktop,
  FaHand,
  FaHandBackFist,
  FaHandPeace,
  FaHandPointer,
  FaHandSpock,
  FaLock,
  FaMoon,
  FaRocket,
  FaSun,
  FaThumbsDown,
  FaThumbsUp,
  FaUniversalAccess,
  FaUser,
  FaWrench,
} from 'react-icons/fa6';

const REGISTRY = {
  // Gestos
  handPaper: FaHand,
  thumbsUp: FaThumbsUp,
  thumbsDown: FaThumbsDown,
  fist: FaHandBackFist,
  peace: FaHandPeace,
  pointer: FaHandPointer,
  spock: FaHandSpock,
  // Interfaz
  lock: FaLock,
  bolt: FaBolt,
  clapper: FaClapperboard,
  wrench: FaWrench,
  desktop: FaDesktop,
  accessible: FaUniversalAccess,
  book: FaBookOpen,
  rocket: FaRocket,
  user: FaUser,
  sun: FaSun,
  moon: FaMoon,
};

export const DEFAULT_ICON = 'handPaper';

export function Icon({ name = DEFAULT_ICON, size = 18, className = '' }) {
  const Component = REGISTRY[name] ?? REGISTRY[DEFAULT_ICON];
  return <Component size={size} className={`icon ${className}`.trim()} aria-hidden="true" focusable="false" />;
}
