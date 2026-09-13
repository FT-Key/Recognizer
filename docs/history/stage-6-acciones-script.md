# Etapa 6 — Acciones script (bloqueante y no bloqueante)

- **Rama:** stage/6-acciones-script
- **Estado:** completada
- **Objetivo:** añadir acciones que ejecuten scripts locales del usuario
  (`.py`, `.ps1`, `.bat`/`.cmd`, `.sh`) disparados por gestos, con modo bloqueante y no
  bloqueante, resolución automática de intérprete y paso opcional del contexto del gesto.

- **Criterios de aceptación:**
  - Nuevo puerto `ScriptRunner` (core) y adaptador `SubprocessScriptRunner` (adapters)
    que resuelve el intérprete por extensión (`auto`) o explícito y ejecuta con
    `shell=False`. ✅
  - Nuevo tipo de acción `script` en `config.yaml` (`path`, `args`, `interpreter`,
    `working_dir`, `blocking`, `timeout_seconds`, `pass_context`). ✅
  - Modo no bloqueante (por defecto) y bloqueante (espera al proceso, con
    `timeout_seconds` obligatorio > 0). ✅
  - Contexto del gesto al script (opt-in) por variables de entorno. ✅
  - Los 4 formatos funcionan; errores se registran como `ActionError` sin tumbar la app. ✅
  - Tests, README, config.yaml, ARCHITECTURE y gate verde. ✅

## Plan
1. Dominio: `ScriptInterpreter`, `ScriptRequest`; puerto `ScriptRunner`.
2. Adaptador `SubprocessScriptRunner` (intérprete por extensión, bloqueante/no bloqueante).
3. Acción `ScriptAction` + config `ScriptActionConfig` + wiring en bootstrap.
4. `config.yaml` con ejemplos comentados de los 4 formatos.
5. Tests y gate; revisión; docs; merge.

## Cambios (archivos)
- `core/domain/action.py`: enum `ScriptInterpreter` y `ScriptRequest` (frozen/slots) con
  `path`, `args`, `interpreter`, `working_dir`, `blocking`, `timeout_seconds`, `env`.
- `core/ports/script_runner.py` (nuevo): puerto `ScriptRunner.run(request)`.
- `core/actions/script.py` (nuevo): `ScriptAction`; construye el env `RECOGNIZER_*` cuando
  `pass_context` y delega en el puerto.
- `core/constants.py`: `CONTEXT_ENV_GESTURE/_HANDEDNESS/_CONFIDENCE/_TIMESTAMP`.
- `adapters/subprocess_script.py` (nuevo): resolución de intérprete (`auto` por extensión),
  argv por formato, env fusionado, `cwd`, `popen`/`run` inyectables, `OSError` y
  `TimeoutExpired` → `ActionError`.
- `core/config.py`: `ScriptActionConfig` (con validador `blocking ⇒ timeout_seconds > 0`)
  añadido a la unión discriminada `ActionConfig`.
- `bootstrap.py`: `script_runner` inyectable (`SubprocessScriptRunner` por defecto) y
  `case ScriptActionConfig` en `_build_action`.
- `config.yaml`: bloque comentado con los 4 formatos y todas las claves.

## Decisiones
- Una sola acción `script` con flag `blocking` (no dos tipos) para no duplicar config.
- `blocking: true` exige `timeout_seconds > 0` (validado en config) para no congelar el
  bucle de cámara de forma indefinida; `blocking: false` (default) es fire-and-forget.
- `interpreter: auto` resuelve por extensión; el resto permite forzar.
- El contexto del gesto viaja por variables de entorno `RECOGNIZER_*` (opt-in).
- `shell=False` en ambos caminos; el `argv` viene de config confiable.

## Tests y gate (resultados reales)
- `uv run test`: **378 passed**, 2 deselected, cobertura **98.81%** (umbral 80%).
- `uv run pytest -m integration --no-cov`: **2 passed**, 378 deselected.
- `uv run lint`: ruff check OK; ruff format OK (92 archivos).
- `uv run typecheck`: mypy strict OK (92 archivos).
- `uv run check-arch`: **3/3** contratos KEPT.
- `uv run smoke --frames 30 --no-window`: **Smoke OK**, 30 fotogramas, 11.5 FPS.
- Tests nuevos: `test_subprocess_script.py` (intérpretes, modos, timeout, env, errores) y
  `test_script_action.py` (contexto opt-in). Ampliados: `test_action_config.py`
  (`ScriptActionConfig` y validaciones) y `test_bootstrap.py` (wiring con doble).

## Revisión (hallazgos y correcciones)
- Hallazgo **mayor** corregido: `blocking=True` sin timeout podía congelar la cámara;
  ahora `ScriptActionConfig` exige `timeout_seconds > 0` si `blocking` (test añadido).
- Menores registrados como pendientes: `-ExecutionPolicy Bypass` de PowerShell no
  configurable; el `Popen` no bloqueante descarta el handle (igual que
  `SubprocessCommandRunner`); en modo bloqueante stdout/stderr van a `DEVNULL` y no se
  registra el `returncode`.

## Commits
_(pendiente)_

## Pendientes / riesgos
- El modo bloqueante detiene el bucle de cámara mientras el script corre: documentado.
- `bash` puede no existir en Windows; `.sh` falla con `ActionError` controlado.
