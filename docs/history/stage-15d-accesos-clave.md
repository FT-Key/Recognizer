# Etapa 15d-accesos-clave — Método y resultado en el registro de accesos

- **Rama:** stage/15d-accesos-clave
- **Estado:** completada
- **Objetivo:** que el registro de accesos distinga logins faciales y con clave,
  registre también los intentos fallidos con clave y los muestre en verde/rojo,
  explicando en el detalle la falta de foto en los accesos con clave.
- **Criterios de aceptación:**
  - [x] `AccessEvent` con `method` (`facial`/`clave`) y `success`; líneas viejas migran a facial exitoso.
  - [x] El login con clave exitosa se registra como `clave`/éxito; el fallido también (con la identidad real si el usuario existe, o el texto ingresado con viewer si no).
  - [x] La tabla muestra Método y Resultado; filas verdes (éxito) y rojas (fallo).
  - [x] El detalle muestra "Inicio con clave exitoso/fallido" o "Inicio facial exitoso" en color y explica la falta de foto con clave.
  - [x] Gate verde.

## Plan
1. Dominio `AccessMethod` + campos en `AccessEvent`; persistencia y migración en el repositorio.
2. Runner: log de éxito con clave y de intentos fallidos (sin cambiar códigos de retorno).
3. Panel de accesos: columnas, colores por tag y detalle con banner de estado.
4. Tests + gate; documentación; merge.

## Cambios (archivos)
- `core/domain/access.py`: `AccessMethod` (`FACE`/`PASSWORD`), `AccessEvent.method`/`success` (defaults para migrar).
- `adapters/file_access_log_repository.py`: claves `method`/`success`; parseo tolerante (desconocido → facial, no-bool → éxito).
- `cli/apps/face_auth.py`: `_append_access_event(..., method=, success=)`; éxito con clave se registra como tal; `_append_failure_event` para intentos fallidos (solo con usuario no vacío; fallo de escritura no cambia el 1).
- `cli/face_access_gui.py`: columnas Método/Resultado, `tag_configure` verde/rojo, banner de estado en el modal y nota "sin foto: el acceso fue con clave, no con cámara".
- `pyproject.toml`: `S105` para `face_access_gui.py` (falsos positivos, como el resto de la UI facial).
- Tests: `test_face_access_log.py` (round-trip, legado, medio desconocido), `test_face_access_gui.py` (columnas, tags, modales), `test_face_password_login.py` (éxito/fallo/desconocido/vacío).

## Decisiones
- `success: bool` en vez de segundo enum: el texto ("éxito"/"fallido") vive en la GUI como constantes.
- El fallo con usuario desconocido guarda el texto ingresado (auditoría) con viewer; nunca la clave.
- Usuario vacío no se registra (equivale a diálogo cancelado).
- El orden de construcción del `access_log` en el éxito no cambió: un registro roto sigue sin bloquear el login.

## Tests y gate (resultados reales)
- `uv run lint` OK; `uv run typecheck` OK (mypy strict, 206 archivos).
- `uv run test` **1258 passed** (cobertura 95.54%).
- `uv run check-arch` 3/3.
- `uv run smoke --frames 30 --no-window` 9.4 FPS.

## Revisión (hallazgos y correcciones)
- Sin reviewer formal (cambio acotado sobre 15d ya revisada); se mantuvo el gate completo verde.

## Commits
- `05f4103` feat(accesos): metodo y resultado en el registro (clave exitosa/fallida en verde/rojo).
- Merge a `dev` con `--no-ff` y push OK (`53ac2ea..8d56106`).

## Pendientes / riesgos
- Verificación manual del usuario: colores y textos del panel de accesos con datos reales.
