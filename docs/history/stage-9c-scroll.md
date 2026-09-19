# Etapa 9c — Scroll con gestos sostenidos

- **Rama:** stage/9c-scroll
- **Estado:** completada
- **Objetivo:** scroll arriba/abajo manteniendo un gesto (sin manos compuestas),
  con puntero congelado y mute reubicado en menú compuesto.
- **Criterios de aceptación:**
  - `Victory` sostenido scrollea arriba; `Closed_Fist` sostenido scrollea abajo. ✅
  - Silenciar pasa al menú `System` (izq `Pointing_Up` + der `Closed_Fist`). ✅
  - Los ticks `GestureHeld` de scroll no disparan scroll cuando hay menú activo. ✅
  - Gate verde: lint, typecheck, pytest >= 80%, check-arch. ✅

## Plan
1. Puerto `MouseController.scroll_by` + `ScrollDirection` en el dominio y `ScrollAction`.
2. `ScrollActionConfig` en config con cooldown por acción y `case scroll` en `bootstrap`.
3. `GestureHeld` resuelve menús en solo lectura (sin scroll fantasma con menú activo).
4. `config.yaml`: mappings `Victory`/`Closed_Fist` + menú `System` para mute.
5. Tests y gate; revisión; docs.

## Cambios (archivos)
- `core/domain/pointer.py`: `ScrollDirection` (arriba/abajo).
- `core/constants.py`: `DEFAULT_SCROLL_LINES=3`, `DEFAULT_SCROLL_REPEAT_SECONDS=0.15`,
  `MIN_SCROLL_LINES`, `SCROLL_FIXED_AXIS`.
- `core/actions/scroll.py` (nuevo): `ScrollAction` (ticks `Held` + repeat, como volumen).
- `core/ports/mouse_controller.py`: `scroll_by`; `adapters/pynput_mouse.py`: `scroll_by`.
- `core/config.py`: `ScrollActionConfig` + unión de acciones.
- `bootstrap.py`: `case scroll`, controller dedicado inyectable, override de cooldown por
  acción con `None`-check (`is not None`).
- `core/actions/dispatcher.py`: `GestureHeld` resuelve menús en solo lectura (no consume
  ni dispara scroll con menú activo).
- `config.yaml`: mappings scroll + menú `System` (izq `Pointing_Up` + der `Closed_Fist`
  → mute).
- Tests: `test_scroll_action.py` (nuevo); ampliados `test_pynput_mouse`,
  `test_action_dispatcher`, `test_bootstrap`, `test_action_config`.

## Decisiones
- Ticks `Held` reutilizan `GestureHeld` + repeat (mismo patrón que volumen).
- Cooldown por acción necesario: el global (1.0 s) daría 1 scroll/seg, inutilizable.
- Puntero congelado gratis: `PointerDetectionProcessor` solo emite con `Pointing_Up`,
  así que `Victory`/`Closed_Fist` no mueven el cursor.
- `config.yaml` es la fuente del cooldown 0.12 (`DEFAULT_SCROLL_COOLDOWN_SECONDS`
  eliminado); constantes centralizadas en `core/constants.py`.

## Tests y gate (resultados reales)
- `uv run test`: **600 passed**, cobertura **95.95%** (umbral 80%).
- `uv run typecheck`: mypy strict OK (**120 archivos**).
- `uv run check-arch`: **3/3** contratos KEPT.
- `uv run lint`: ruff check OK; ruff format falla solo en
  `docs/DESKTOP-SIMPLIFICADO.md` (preexistente, no tocado por la etapa).
- Smoke con cámara real: pendiente.

## Revisión (hallazgos y correcciones)
- 2 hallazgos no bloqueantes, ambos corregidos: override de cooldown con `is not None`
  (un `0` explícito no debe caer al global) y centralización de constantes en
  `core/constants.py`, eliminando `DEFAULT_SCROLL_COOLDOWN_SECONDS` en favor de
  `config.yaml` como fuente del 0.12.

## Commits
_(pendiente — rama stage/9c-scroll sin mergear a dev)_

## Pendientes / riesgos
- Calibrar `lines`/`repeat`/`cooldown` con uso real.
- Verificación manual con cámara: scroll arriba/abajo, mute compuesto y ausencia de
  scroll fantasma en menús (añadir a `docs/PENDING-TESTS.md` siguiendo el patrón
  existente); smoke con cámara pendiente.
