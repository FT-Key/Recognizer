# Fix 15b-2 — Contraste del overlay facial + cierre del submenú (cuelgue)

- **Rama:** stage/15b-fix2-face-ux
- **Estado:** completada
- **Objetivo:** el texto del overlay facial se lee sobre video; cerrar el submenú facial ("Volver"/ESC/X) regresa al menú principal sin colgar el proceso.
- **Criterios de aceptación:**
  - [x] HUD, guía, etiquetas de caja y marco objetivo con contraste (panel oscuro + texto claro).
  - [x] "Volver"/ESC/X del submenú vuelve al menú principal sin cuelgue.
  - [x] Gate verde: lint, typecheck, pytest ≥80%, check-arch 3/3.

## Causa raíz
- **Cuelgue:** `run_face_submenu` usaba `Toplevel.mainloop()` anidado dentro del `mainloop()` de
  la raíz. Al destruir el Toplevel, la raíz seguía viva (oculta) y el bucle anidado nunca
  retornaba → ventana cerrada y proceso colgado sin interfaz (Ctrl+C tampoco respondía).
- **Texto ilegible:** HUD/guía usaban gris `SURFACE_COLOR_BGR` sobre el video.

## Cambios (archivos)
- `cli/face_menu_gui.py`: `window.mainloop()` → `window.wait_window()` (espera solo a ese Toplevel).
- `adapters/overlay_face.py`: helper `_draw_panel_text` (panel oscuro + borde de color + texto
  claro) para HUD, progreso, guía, etiqueta de caja y marco objetivo.
- `tests/unit/test_face_menu_gui.py`: `FakeToplevel.wait_window` y aserción `wait_window_calls == 1`.

## Decisiones
- `wait_window` en lugar de `mainloop` anidado: patrón correcto para subdiálogos sobre una raíz viva.
- Contraste por panel oscuro (20,20,20) + texto blanco/verde; el color de estado queda en el borde.

## Tests y gate (resultados reales)
- `uv run lint`: OK (208 archivos). `uv run typecheck`: OK (183). `uv run test`: **1119 passed** (94.67%). `uv run check-arch`: 3/3.
- Render de verificación (`face_overlay_preview.png`) con paneles legibles.

## Revisión (hallazgos y correcciones)
- Fix de causa raíz; pendiente `/stage-review` si el usuario lo pide.

## Commits
- Pendiente `git-ops`.

## Pendientes / riesgos
- Calibrar `min_face_width_ratio`/`match_threshold` con cámara real; probar selector con 2 cámaras.
