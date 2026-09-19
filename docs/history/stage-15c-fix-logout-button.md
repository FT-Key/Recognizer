# Fix 15c-4 — "Cerrar sesión" al final, en rojo y con confirmación

- **Rama:** stage/15c-fix-logout-button
- **Estado:** completada
- **Objetivo:** mover "Cerrar sesión" al final del submenú facial, pintarlo en rojo y pedir
  confirmación para evitar clicks accidentales.
- **Criterios de aceptación:**
  - [x] "Cerrar sesión" va al pie, a la derecha de "Volver", en rojo (`theme.danger`).
  - [x] `messagebox.askyesno` confirma antes de cerrar; cancelar no ejecuta el runner.
  - [x] Gate verde.

## Cambios (archivos)
- `cli/face_menu_gui.py`: `_make_button(..., danger=True)` (rojo), botón de logout movido al
  pie (`footer_actions`), re-empaquetado para quedar al final, y confirmación en `do_logout`.
- `tests/unit/test_face_menu_gui.py`: test de cancelación (no llama al runner).

## Tests y gate (resultados reales)
- `uv run lint`: OK. `uv run typecheck`: OK (201). `uv run test`: **1207 passed** (95.46%).
- `uv run check-arch`: 3/3.

## Commits
- Pendiente `git-ops`.
