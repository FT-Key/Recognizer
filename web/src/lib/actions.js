/**
 * Recognizer Web — Dispatcher de acciones.
 * Mapea gestos estabilizados a acciones del navegador con cooldown por gesto.
 */

import { CONFIG } from './config.js';
import * as YT from './youtube-controller.js';
import { createNavigator } from './navigation.js';

export function createDispatcher({ onAction } = {}) {
  const navigator = createNavigator();
  const cooldowns = {};

  function canDispatch(gestureName) {
    const now = Date.now();
    const last = cooldowns[gestureName] || 0;
    return now - last >= CONFIG.actions.cooldownMs;
  }

  function dispatchYouTube(command) {
    switch (command) {
      case 'play_pause':
        YT.togglePlayPause();
        break;
      case 'volume_up':
        YT.volumeUp();
        break;
      case 'volume_down':
        YT.volumeDown();
        break;
      case 'mute':
        YT.toggleMute();
        break;
      default:
        break;
    }
  }

  function dispatchNavigation(command, url) {
    switch (command) {
      case 'new_tab':
        navigator.openNewTab();
        break;
      case 'scroll_up':
        navigator.scrollUp();
        break;
      case 'scroll_down':
        navigator.scrollDown();
        break;
      case 'open_url':
        navigator.openNewTab(url);
        break;
      default:
        break;
    }
  }

  function dispatch(gestureName, confidence, handedness) {
    const mapping = CONFIG.actions.mappings[gestureName];
    if (!mapping) return;
    if (!canDispatch(gestureName)) return;

    cooldowns[gestureName] = Date.now();

    if (mapping.action === 'youtube') {
      dispatchYouTube(mapping.command);
    } else if (mapping.action === 'navigation') {
      dispatchNavigation(mapping.command, mapping.url);
    }

    onAction?.(mapping, { confidence, handedness });
  }

  function reset() {
    for (const key of Object.keys(cooldowns)) delete cooldowns[key];
  }

  return { dispatch, reset };
}
