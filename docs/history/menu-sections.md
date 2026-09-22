# Menú por secciones (principal + "Otras apps")

- **Rama:** `dev` (cambios sin commitear; ver "Commits")
- **Estado:** completada
- **Objetivo:** dejar en el menú principal solo las apps más útiles y mover el resto a un
  submenú "Otras apps" (incluidas las que aún no existen), para que el launcher no mezcle
  todo en una lista larga.
- **Criterios de aceptación:**
  - [x] El menú principal lista gestos, contador de personas, anti-intrusos, facial, zona
    permanencia y zona vacía.
  - [x] Al final hay una entrada "Otras apps" que abre un submenú.
  - [x] El submenú lista las secundarias y las no creadas (EPP, inventario).
  - [x] Funciona en la GUI (vintage) y en la consola.
  - [x] Gate verde.

## Cambios (archivos)

- `core/domain/app.py`: nuevo `AppGroup` (`MAIN`/`OTHER`) y campo `group` en `AppInfo`
  (por defecto `OTHER`); `AppCatalog.apps_in_group(group)`. Se marcaron `MAIN` las seis apps
  pedidas.
- `cli/menu_gui.py`:
  - `build_menu_rows(..., group=...)`: lista el grupo y, para `MAIN`, agrega la fila
    "Otras apps" (`MenuRow.opens_other_apps`).
  - `_open_app` y `_build_app_rows`: lógica de abrir app y de pintar filas, compartidas por
    el menú principal y el submenú.
  - `run_other_apps_submenu`: `Toplevel` con las apps de `OTHER`, "Volver" y ESC para
    regresar.
  - El `resolve_runner` se importa dentro de `_open_app` (perezoso) para que los tests puedan
    parchearlo en `cli.menu`.
- `cli/menu.py` (consola): `render_catalog(group=...)` y `run_menu` con submenú (opción
  "Otras apps" → bucle del grupo `OTHER`; "0" = Volver). `_launch_info` centraliza el
  lanzamiento.
- Tests: `test_app_domain.py` (grupos), `test_menu.py` (render por grupo y submenú),
  `test_menu_gui.py` (badges del principal y submenú), `test_face_menu_gui.py` (fila facial
  del grupo `MAIN`).

## Decisiones

- El agrupamiento es **dominio puro** (`AppGroup` en el catálogo), no de la UI: la GUI y la
  consola lo consumen.
- `build_menu_rows`/`render_catalog` mantienen el default sin agrupar (`group=None`) para no
  romper el resto de usos; el menú principal pasa `group=AppGroup.MAIN` explícito.
- El submenú reutiliza el mismo render de filas (extraído a `_build_app_rows`) y la misma
  lógica de apertura (`_open_app`), en vez de duplicar el menú.

## Tests y gate (resultados reales)

- `uv run lint`: OK. `uv run typecheck`: OK (252 archivos). `uv run test`: **1581 passed**
  (93.97%). `uv run check-arch`: 3/3.

## Commits

- Pendiente `git-ops` (todo el trabajo de las etapas 20/22/23 y estos fixes sigue sin
  commitear en `dev`).

## Pendientes / riesgos

- Verificación manual del aspecto del submenú (tamaño de ventana, foco y rueda del ratón) en
  el menú vintage real.
