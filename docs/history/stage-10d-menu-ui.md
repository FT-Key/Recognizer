# Etapa 10d — Rediseño UX/UI del menú de escritorio (vintage)

- **Rama:** stage/10d-menu-ui
- **Estado:** completada
- **Objetivo:** rediseñar el menú de escritorio con la estética "Vintage" de la web
  (paleta teal/plata, biseles skeuomórficos, tipografía pixel), ventana más grande y
  espaciada, cada app como botón, e icono del logo (mismo `minilogo` de la web) en la
  barra de título y de tareas.
- **Criterios de aceptación:**
  1. Ventana más grande y espaciada (alto adaptativo al nº de apps, clamp a pantalla);
     cada app es un botón. ✅
  2. Estética vintage alineada a `web/src/styles/theme.css` (teal `#008080`, superficie
     `#c0c0c0`, biseles, texto negro) con contraste WCAG AA. ✅
  3. Tipografía pixel (Silkscreen, OFL) con fallback a monoespaciada del sistema. ✅
  4. Icono `minilogo` en barra de título y de tareas. ✅
  5. Assets versionados en `assets/` y empaquetados en el `.exe` (spec `datas` + `icon`). ✅
  6. Estados visibles (disponible/deshabilitada/próximamente) y navegación por teclado
     (flechas, Enter/espacio, ESC, Tab) con foco visible. ✅
  7. Sin imports pesados al abrir el menú; fallback a consola intacto. ✅
  8. Gate verde (`lint`, `typecheck`, `test`, `check-arch`). ✅

## Plan
1. Assets: `scripts/build_assets.py` genera `assets/minilogo*.png/.ico` desde
   `web/public/minilogo.png`; fuente Silkscreen (Regular/Bold) + OFL versionadas.
2. `cli/paths.py`: resolución de `assets/` (fuente y `frozen` vía `sys._MEIPASS`).
3. `cli/menu_gui.py`: rediseño (tema, cabecera con logo, apps como botones, badges,
   atajos de teclado, icono, alto adaptativo).
4. `packaging/recognizer.spec`: `datas` de `assets/` + `icon` del `.exe`.
5. Tests con dobles (sin display) + gate completo.

## Cambios (archivos)
- `assets/` (nuevo): `minilogo.png/.ico/-128/-64`, `Silkscreen-Regular/Bold.ttf`, `OFL.txt`.
- `scripts/build_assets.py` (nuevo): genera icono y logo escalado desde el logo de la web.
- `src/recognizer/cli/paths.py`: `ASSETS_DIRNAME`, `assets_dir()`, `desktop_icon_path()`,
  `desktop_logo_path()`, `display_font_paths()` (tolerantes; `_MEIPASS` en frozen).
- `src/recognizer/cli/menu_gui.py`: rediseño completo (tokens `MenuTheme`, cabecera con
  logo, apps como botones con `wraplength`, badges por estado, `compute_window_geometry`
  adaptativo con clamp y Canvas+Scrollbar, icono, navegación por teclado, branding tolerante).
- `packaging/recognizer.spec`: `datas` de `assets/` y `icon=assets/minilogo.ico`.
- `tests/unit/test_menu_gui.py`: migrado a botones (26 tests) y `tests/unit/test_paths.py` (nuevo).

## Decisiones
- **Widgets clásicos `tk` (no ttk):** en Windows ttk ignora `bg`, así que la estética
  skeuomórfica (biseles, colores) se logra con `tk.Frame/Label/Button`.
- **Tipografía pixel:** Silkscreen (OFL) se registra en Windows con
  `ctypes.windll.gdi32.AddFontResourceExW(FR_PRIVATE)`; si falla, fallback a
  `Courier New`. Cuerpo en `Consolas` con fallback. El branding falla en silencio:
  un asset ausente nunca tumba el menú.
- **Alto adaptativo:** `compute_window_geometry(row_count, screen_w, screen_h)` puro
  calcula alto según filas y lo clampa al 90% de la pantalla; la lista va en un
  `Canvas` con scrollbar para que ninguna fila se recorte al achicar.
- **Icono:** `iconbitmap` (.ico) → `iconphoto` (.png) → sin icono; el `PhotoImage` se
  retiene en `_Branding.icon` para que el GC no lo recolecte.
- **Contraste (WCAG AA):** `badge_foreground` usa blanco sobre teal (4.77:1) y texto
  negro sobre warning/neutral (6.6:1 / 5.3:1); el subtítulo de cabecera pasa a blanco.
- **Testabilidad:** widgets resueltos como `tkinter.X` en tiempo de llamada y
  `tk_factory` inyectable; la lógica pura (`build_menu_rows`, `compute_window_geometry`,
  `badge_foreground`) no toca tkinter.
- **Assets bundleados por el spec** (no como recursos editables): el usuario no los
  edita; `build_exe.py` no cambia.

## Tests y gate (resultados reales)
- `uv run test`: **714 passed, 2 deselected, cobertura 96.17%** (mínimo 80%).
- `uv run lint`: ruff check + format OK — **160 files already formatted**.
- `uv run typecheck`: mypy --strict OK — **no issues found in 135 source files**.
- `uv run check-arch`: import-linter OK — **3 kept, 0 broken**.
- Smoke real de construcción Tk (crear→`update()`→`destroy()`, sin `mainloop`): OK,
  `run_gui_menu` retorna 0; assets e icono resueltos en modo fuente.

## Revisión (hallazgos y correcciones)
- 3 bloqueantes de contraste WCAG AA (badges coming-soon/disabled y subtítulo) →
  corregidos con `badge_foreground` y subtítulo en blanco.
- Infos corregidos: retención anti-GC del icono, clamp de ancho a pantalla,
  `WRAPLENGTH_MIN`/`TK_BREAK`/`TK_ALL` como constantes, `with` en `build_assets.py`.
- Infos no bloqueantes pendientes: cobertura de `_apply_window_icon` con assets
  presentes/`iconbitmap` fallando; doble fuente de verdad geometría vs `MenuTheme`;
  `except Exception` amplio en branding (justificado por tolerancia).

## Commits
- Pendiente (los crea `git-ops` al cerrar la etapa).

## Pendientes / riesgos
- **Verificación visual del usuario** con display real (tamaño, colores, icono en la
  barra de tareas, navegación por teclado); no verificable de forma automática.
- `.exe`: el icono y los assets van bundleados por spec; falta regenerar y probar el
  `.exe` (torch/YOLO siguen excluidos, bundle ~1 GB).
- Silkscreen se registra en Windows; en otros SO el menú usa la fuente de respaldo.
