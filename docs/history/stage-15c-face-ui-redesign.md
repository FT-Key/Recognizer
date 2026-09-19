# Fix 15c-3 — Rediseño del submenú facial y detalle de usuarios

- **Rama:** stage/15c-face-ui-redesign
- **Estado:** completada
- **Objetivo:** corregir la inconsistencia de sesión, mover Nombre/Rol a un formulario de
  enrolamiento propio, mejorar el layout del submenú y dar a la lista de usuarios un "Ver
  detalle" modal con la foto y las acciones de editar/re-enrolar.
- **Criterios de aceptación:**
  - [x] Header con **una sola** línea de sesión correcta (bug: `role_label` duplicado).
  - [x] Nombre/Rol viven en `face_enroll_gui` (formulario propio), no en el submenú.
  - [x] Submenú con tarjeta de sesión y panel de login (mejor uso del espacio).
  - [x] Panel de usuarios: "Ver detalle" abre modal con foto + Editar + Re-enrolar.
  - [x] Gate verde.

## Causa raíz
En `face_menu_gui.py` la variable `role_label` se definía dos veces (label de sesión del header
y label "Rol" del formulario) y se pisaban: el header quedaba en "invitado (viewer)" y el
"Rol" del formulario mostraba "Sesión: Franco (admin)".

## Cambios (archivos)
- `cli/face_adapters.py`: `allowed_roles`, `default_enroll_role`, `store_is_empty` compartidos.
- `cli/face_enroll_gui.py` (nuevo): formulario Nombre/Rol con permiso y cola `[nombre, rol]`.
- `cli/face_menu_gui.py`: `session_label` único (deriva el rol real, sin "(viewer)" fijo),
  tarjeta de sesión + panel de login, botones agrupados; Enrolar abre el formulario.
- `cli/face_users_gui.py`: sin vista previa inline; "Ver detalle" modal (`grab_set`) con foto,
  datos y Editar/Re-enrolar; Eliminar queda en la lista.
- Tests: `test_face_menu_gui.py`, `test_face_users_gui.py`, `test_face_enroll_gui.py`.

## Decisiones
- El header y la tarjeta usan la misma `Identity` fresca (`state["identity"]`) para no divergir.
- El formulario de enrolamiento es una ventana aparte: responsabilidad separada del menú.
- Modal de detalle con `grab_set`/`wait_window`, como el visor de accesos.

## Tests y gate (resultados reales)
- `uv run lint`: OK. `uv run typecheck`: OK (201). `uv run test`: **1206 passed** (95.46%).
- `uv run check-arch`: 3/3.

## Revisión (hallazgos y correcciones)
- Reviewer: requiere cambios → corregido el hallazgo mayor (rol hardcodeado en el header del
  invitado) derivando la línea de sesión de `identity.role.value` y reutilizando la identidad
  fresca; añadido test de que el formulario no se abre hasta pulsar Enrolar.

## Commits
- Pendiente `git-ops`.
