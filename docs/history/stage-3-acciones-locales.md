# Etapa 3 — Acciones locales: teclado/multimedia y comandos

- **Rama:** stage/3-acciones-locales
- **Estado:** completada (gate verde; commits de cierre y merge pendientes)
- **Objetivo:** disparar acciones locales (multimedia, atajos de teclado y comandos)
  al confirmarse un gesto (`GestureDetected`), con decoradores gated/debounced/logged y
  un entrypoint de app local (`recognizer`) además del `smoke`.
- **Criterios de aceptación:**
  - `ActionsConfig` en `config.yaml` mapea gestos (excepto `None`) a acciones tipadas:
    `media_key` (enum `MediaKey`), `hotkey` (tuplas de teclas) y `command` (argv sin shell).
  - Evento `GestureDetected` -> dispatcher ejecuta la acción mapeada una vez por evento;
    `GestureReleased` no dispara nada; gesto sin mapeo es no-op (Null Object).
  - Cadena `Gated(Debounced(Logged(action)))`: el gate se puede desactivar/activar en vivo,
    el debounce respeta `cooldown_seconds` con reloj inyectable y el log registra cada
    ejecución; un `ActionError` se registra y no tumba el loop.
  - Adaptadores: `PynputKeySender` (controller inyectable) para multimedia/atajos y
    `SubprocessCommandRunner` (Popen inyectable, `shell=False`) para comandos.
  - Entrypoint `uv run recognizer` con flags `--config`, `--device`, `--frames`,
    `--no-window`, `--no-actions`; ESC/q sale, `a` alterna el gate; overlay de gestos igual.
  - Gate verde: lint, typecheck, test (cobertura >= 80%) y check-arch.
  - Smoke real `uv run smoke --frames 30 --no-window` sin regresión.

## Plan
1. Dominio: `ActionContext`, `MediaKey`, puerto `Action`; errores `ActionError`.
2. Puertos `KeySender` y `CommandRunner`; acciones core `MediaKeyAction`, `HotkeyAction`,
   `CommandAction`, `NoOpAction`.
3. Decoradores core `LoggedAction`, `DebouncedAction`, `GatedAction` y
   `GestureActionDispatcher`.
4. Config pydantic (`ActionsConfig` + union discriminada) y `config.yaml`.
5. Adaptadores `PynputKeySender` y `SubprocessCommandRunner`.
6. `bootstrap.py` (factory desde config) y CLI `recognizer` (`cli/app.py`).
7. Tests unitarios sin hardware, gate, revisión y cierre.

## Cambios (archivos)
- `src/recognizer/core/domain/action.py` (nuevo): enum `MediaKey`, `ActionContext`
  (gesto, confianza, lateralidad, timestamp) y protocolo `Action` (Command).
- `src/recognizer/core/ports/key_sender.py` y `core/ports/command_runner.py` (nuevos):
  puertos `KeySender` (tecla multimedia/atajo) y `CommandRunner` (argv).
- `src/recognizer/core/actions/` (nuevo): `local.py` (`MediaKeyAction`, `HotkeyAction`,
  `CommandAction`), `noop.py` (`NoOpAction`), `decorators.py` (`ActionGate`,
  `LoggedAction`, `DebouncedAction`, `GatedAction`) y `dispatcher.py`
  (`GestureActionDispatcher`).
- `src/recognizer/adapters/pynput_keys.py` (nuevo): `PynputKeySender` con `Controller`
  inyectable y mapeo `MediaKey` -> `pynput.keyboard.Key`.
- `src/recognizer/adapters/subprocess_command.py` (nuevo): `SubprocessCommandRunner`
  con `Popen` inyectable y `shell=False`.
- `src/recognizer/bootstrap.py` (nuevo): composition root con `ActionBindings`,
  `build_pipeline`, `resolve_camera_config` y `build_action_bindings`.
- `src/recognizer/cli/runtime.py` (nuevo): `run_camera_loop` + `RuntimeCallbacks`
  (bucle de cámara compartido por smoke y app).
- `src/recognizer/cli/app.py` (nuevo): entrypoint `recognizer` con flags `--config`,
  `--device`, `--frames`, `--no-window`, `--no-actions` y HUD de acciones (tecla `a`).
- Modificados: `core/errors.py` (`ActionError`), `core/constants.py`
  (`DEFAULT_ACTION_COOLDOWN_SECONDS`, `ACTION_LOGGER_NAME`), `core/config.py`
  (`ActionsConfig` + unión discriminada por `type`), `cli/smoke.py` (delega en
  `bootstrap`/`runtime` sin cambiar flags ni logs), `pyproject.toml` (script
  `recognizer`) y `config.yaml` (sección `actions` con 5 mapeos y ejemplo `command`
  comentado).

## Decisiones
- Un único `ActionGate` compartido por todas las acciones (todos los `GatedAction` lo
  referencian) para poder activar/desactivar en vivo con la tecla `a`.
- Cadena `Gated(Debounced(Logged(action)))`: el debounce aplica el cooldown global y el
  log registra cada ejecución que llega a la acción.
- `GestureActionDispatcher` usa `NoOpAction` (Null Object) como fallback y captura
  `ActionError`: lo registra como warning y el loop continúa.
- Config pydantic con unión discriminada por `type` y `extra="forbid"`; `mappings`
  rechaza el gesto `None`.
- Adaptadores con dependencia inyectable (controller de pynput / popen) para testear sin
  hardware; los comandos usan `shell=False` con argv de config.
- El smoke se refactoriza sobre `bootstrap.build_pipeline` + `cli.runtime.run_camera_loop`
  para compartir el bucle con la app, sin cambiar flags/logs; el smoke NO ejecuta acciones.

## Tests y gate (resultados reales)
- `uv run lint`: OK (ruff check + format, 95 archivos).
- `uv run typecheck`: OK (mypy strict, 71 archivos).
- `uv run test`: 208 passed + 2 deselected, cobertura 98.57% (umbral 80%); 10 archivos de
  test nuevos con 73 casos.
- `uv run check-arch`: 3/3 contratos KEPT.
- `uv run smoke --frames 30 --no-window`: OK real (30 fotogramas, 15.0 FPS, 0 manos).
- App real: `python -m recognizer.cli.app --no-window --frames 15`: OK (15 fotogramas,
  10.1 FPS, acciones activadas).
- Nota de entorno: en esta sesión `uv` no está en el PATH; el gate se ejecutó con los
  ejecutables del `.venv` (mismos comandos).

## Revisión (hallazgos y correcciones)
- Veredicto del `reviewer`: "apto para merge", sin bloqueantes.
- Corregidos: (a) `resolve_camera_config` pasa a keyword-only (`*, app_config,
  device_override`) y se ajustan llamadas y tests; (b) el error de comando ya no loguea
  el argv completo, solo el programa.
- Nits no corregidos: `build_action_bindings` instancia ambos adapters aunque el mapeo
  use uno solo (coste trivial); literales de estado en `cli/app.py` (código de
  presentación omitido de cobertura); `omit` de `cli/*` en cobertura es política
  pre-existente.

## Commits
- Pendiente: commits de cierre (`feat`, `docs`) y merge `--no-ff` a `dev`; los hashes se
  registran al publicar.

## Pendientes / riesgos
- Verificación manual de acciones reales: pulsar teclas multimedia/atajo y lanzar un
  comando descomentando el ejemplo de `config.yaml`.
- Verificación manual de `Victory`/`Open_Palm` y FPS de etapas 1-2 sigue pendiente.
- Los comandos configurados se ejecutan de verdad: el ejemplo va comentado en config.yaml.
