# Etapa 15d-intento-id — Detalle del intento y IDs no secuenciales

- **Rama:** stage/15d-intento-id
- **Estado:** completada
- **Objetivo:** (1) que el acceso guarde qué ID/DNI se ingresó (nunca la clave)
  y por qué falló (usuario desconocido vs clave incorrecta), visible en tabla y
  detalle; (2) que los IDs de rostro sean aleatorios y no secuenciales para que
  no se infiera orden ni admin (`F-0001`).
- **Criterios de aceptación:**
  - [ ] `AccessEvent` con `attempted` (texto ingresado) y `reason` (motivo); migran a `""`/`None`.
  - [ ] Fallo con usuario existente → `clave incorrecta`; con desconocido → `ID/DNI desconocido` (con el texto ingresado).
  - [ ] Tabla Resultado muestra el motivo en rojo; detalle con Ingresó y Motivo.
  - [ ] IDs nuevos tipo `F-A3F9` (4 alfanuméricos sin ambiguos, CSPRNG, sin colisiones); legado `F-0001` sigue válido.
  - [ ] Gate verde.

## Plan
1. Dominio access: `attempted` + `AccessFailureReason`; persistencia y migración.
2. Runner: registrar intento y motivo en éxito y fallo.
3. Dominio face: `new_face_id` aleatorio; repo/puerto/runner (`new_id`).
4. GUI accesos: Resultado con motivo, detalle con Ingresó/Motivo.
5. Tests + gate; documentación; merge.

## Cambios (archivos)
- `core/domain/access.py`: `AccessEvent.attempted` + `AccessFailureReason` (`UNKNOWN_USER`/`WRONG_PASSWORD`, `reason` default `None`).
- `adapters/file_access_log_repository.py`: claves `attempted`/`reason` + migración a `""`/`None`; validación de IDs con `re.fullmatch`.
- `cli/apps/face_auth.py`: éxito con clave guarda lo ingresado; `_append_failure_event` guarda intento + motivo (desconocido vs clave incorrecta); docstrings al día.
- `core/domain/face.py`: `new_face_id` aleatorio (`F-` + 4 de `FACE_ID_ALPHABET`, CSPRNG inyectable, acotado); reemplaza `next_face_id` secuencial.
- `core/constants.py`: `FACE_ID_ALPHABET` (sin 0/O/1/I/L), `MAX_FACE_ID_ATTEMPTS`.
- `core/ports/face_repository.py` + `adapters/file_face_repository.py`: `next_id` → `new_id`; patrón `^F-[A-Z0-9]{4}$` (legado válido).
- `cli/face_access_gui.py`: Resultado con motivo en rojo, detalle con Ingresó/Motivo.
- Tests: motivo/intento (log, GUI, login), IDs aleatorios (formato, colisiones, migración) y renombres.

## Decisiones
- El motivo se guarda explícito (la GUI de accesos no tiene el almacén de rostros para derivarlo).
- La clave jamás se persiste ni se muestra; solo el identificador tipeado.
- El ID sigue corto y tipeable (4 caracteres) pero sin orden: ya no delata quién es admin ni cuántos hay.
- El puerto renombra `next_id` → `new_id` porque "siguiente" mentía (ya no hay secuencia).

## Tests y gate (resultados reales)
- `uv run lint` OK; `uv run typecheck` OK (mypy strict, 206 archivos).
- `uv run test` **1284 passed** (cobertura 95.58%).
- `uv run check-arch` 3/3.
- `uv run smoke --frames 30 --no-window` OK.

## Revisión (hallazgos y correcciones)
- Reviewer: apta. Aplicados: docstrings (`F-XXXX`, índice sin "contador máximo") y `re.fullmatch` en el patrón de ID.

## Commits
- `feat(accesos)`: intento + motivo y IDs aleatorios (esta rama, merge `--no-ff` a `dev`, push).

## Pendientes / riesgos
- Verificación manual: tabla/detalle de accesos con un fallo real de cada tipo.
