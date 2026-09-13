# Etapa 7 — Acción abrir enlaces (playlist secuencial)

- **Rama:** stage/7-abrir-enlaces
- **Estado:** completada
- **Objetivo:** nueva acción `open_links` que abre enlaces en el navegador (Chrome) de
  forma secuencial (no aleatoria) a partir de una lista configurable, reutilizando la
  ventana de Chrome si ya está abierto. Primer uso: gesto `ILoveYou`.

- **Criterios de aceptación:**
  - Nuevo puerto `LinkOpener` (core) + adaptador `ChromeLinkOpener` (adapters) que abre la
    URL en Chrome: si Chrome ya está abierto, se abre en una pestaña nueva; si no, lo
    lanza y navega a la URL.
  - Acción `open_links` con `urls: [..]` que recorre la lista en orden (índice rotatorio),
    sin aleatoriedad; mapeable a cualquier gesto.
  - `ILoveYou` queda mapeado por defecto al enlace acordado
    (`https://www.youtube.com/watch?v=mlabBbn_fHI&t=0s`).
  - Ruta de Chrome autodetectada (o configurable con `browser`); si no se encuentra,
    `ActionError` controlado y la app sigue.
  - Tests, config.yaml, README y gate verde.

## Plan
1. Dominio: nada nuevo salvo la config; puerto `LinkOpener`.
2. Adaptador `ChromeLinkOpener` (autodetección de Chrome, lanzamiento `shell=False`).
3. Acción `OpenLinksAction` (playlist rotatoria) + config `OpenLinksActionConfig` + wiring.
4. `config.yaml`: `ILoveYou -> open_links` con la lista de enlaces.
5. Tests y gate; revisión; docs; merge.

## Cambios (archivos)
- `core/ports/link_opener.py` (nuevo): puerto `LinkOpener.open(url)`.
- `core/actions/links.py` (nuevo): `OpenLinksAction` con índice rotatorio en memoria.
- `core/config.py`: `OpenLinksActionConfig` (`urls`, `browser`) con validación de URL
  (`http(s)` + host) y en la unión discriminada `ActionConfig`.
- `core/constants.py`: prefijos `HTTP_URL_PREFIX`/`HTTPS_URL_PREFIX`/`URL_PREFIXES`.
- `adapters/chrome_link_opener.py` (nuevo): autodetección de Chrome (PATH + rutas
  habituales de Windows) y lanzamiento `chrome.exe <url>` con `shell=False`; `popen`
  inyectable; `OSError`/`ValueError` → `ActionError`.
- `bootstrap.py`: `link_opener` inyectable (`ChromeLinkOpener` por defecto) y
  `case OpenLinksActionConfig` (usa `browser` si se define).
- `config.yaml`: `ILoveYou -> open_links` activo con la playlist y comentario de `browser`.
- `scripts/actions/log_gesture.py` (nuevo): ejemplo de script de usuario que registra el
  contexto `RECOGNIZER_*` en un log; `.gitignore` ignora su salida.

## Decisiones
- "No aleatorio" = rotación secuencial: cada gesto confirmado abre el siguiente enlace y
  vuelve al principio al agotar la lista. El índice vive en memoria (se reinicia al
  arrancar la app); persistirlo queda como mejora futura.
- No hace falta detectar el proceso de Chrome: `chrome.exe <url>` abre una pestaña en la
  instancia en ejecución o lanza Chrome si no lo está (comportamiento propio del navegador).
- El ejecutable se autodetecta y se puede forzar con `browser`.

## Tests y gate (resultados reales)
- `uv run test`: **399 passed**, 2 deselected, cobertura **98.86%** (umbral 80%).
- `uv run pytest -m integration --no-cov`: **2 passed**, 399 deselected.
- `uv run lint`: ruff check OK; ruff format OK (127 archivos).
- `uv run typecheck`: mypy strict OK (97 archivos).
- `uv run check-arch`: **3/3** contratos KEPT.
- `uv run smoke --frames 30 --no-window`: **Smoke OK**, 30 fotogramas, 17.1 FPS.
- Tests nuevos: `test_open_links_action.py` (rotación, URL única, lista vacía, índice que
  no avanza si falla el opener) y `test_chrome_link_opener.py` (argv, autodetección,
  errores); ampliados `test_action_config.py` y `test_bootstrap.py`.

## Revisión (hallazgos y correcciones)
- Sin hallazgos bloqueantes ni mayores. Menores corregidos: (1) el adaptador captura
  también `ValueError` además de `OSError`; (2) validación de URL más estricta
  (`http(s)` + host con `urlparse`); (3) test que fija que el índice no avanza si el
  opener falla (se reintenta la misma URL).

## Commits
_(pendiente)_

## Pendientes / riesgos
- Solo se integra Chrome por ahora (el adaptador se llama `ChromeLinkOpener`); otros
  navegadores requerirían otro adaptador o configurarlos con `browser`.
- El índice de la playlist no persiste entre ejecuciones.
- Pendiente decidir la nueva funcionalidad de `Pointing_Up` y `Victory`.
