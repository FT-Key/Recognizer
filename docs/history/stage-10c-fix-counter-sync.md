# Etapa 10c-fix — Contador de personas: conteo sincronizado

- **Rama:** `stage/10c-fix-counter-sync`
- **Estado:** completada
- **Objetivo:** reducir el descuadre `Entradas`/`Salidas` del contador. Hoy una persona
  que aparece cerca de la línea y se mueve genera cruces fantasma (nace ya de un lado y
  al moverse cuenta solo una dirección), y el jitter del centro cuenta de más.
- **Criterios de aceptación:**
  - [x] `CountingLine` con **banda muerta (hysteresis)** `margin`: el centro debe superar
    `position ± margin` para tener un lado confirmado; dentro de la banda no hay lado.
  - [x] Un track que **nace dentro de la banda** no cuenta hasta confirmar un lado
    (elimina cruces fantasma de quien aparece junto a la línea).
  - [x] **Purga por timeout** (`track_timeout_frames`): el estado de un track no visto en
    N fotogramas se elimina; si reaparece se trata como nuevo (sin cruce fantasma).
  - [x] Config `people_counter.line.margin` y `track_timeout_frames` + defaults en
    `core/constants.py` + `config.yaml`.
  - [x] Overlay dibuja la banda muerta (líneas de margen) para calibrar visualmente.
  - [x] Tests sin hardware + gate verde (lint, typecheck, pytest, check-arch).
  - [x] Revisión del reviewer aplicada; docs/STATE actualizados.

## Plan

1. Dominio: `CountingLine.zone()` (con `margin`) y `LineCrossingCounter` (banda muerta,
   lado `SIDE_UNKNOWN`, purga por timeout) en `core/domain/tracking.py`.
2. Config: `CountingLineConfig.margin`/`track_timeout_frames`; constantes.
3. Overlay: dibujar la banda de margen en `adapters/overlay_people.py`.
4. Runner: pasar `track_timeout_frames` al contador.
5. Tests, gate completo, revisión, docs.

## Cambios (archivos)

Modificados:
- `src/recognizer/core/domain/tracking.py`: `CountingLine` gana `margin` y `zone()`
  sustituye a `side()`; `SIDE_UNKNOWN` dentro de la banda muerta. `LineCrossingCounter`
  aplica banda muerta, fija el lado inicial de forma inmediata en el primer fotograma fuera
  de banda, usa `confirm_frames` solo para cambios de lado y purga los tracks no vistos
  durante `track_timeout_frames`. Eliminado un guard muerto.
- `src/recognizer/core/config.py`: campos `margin` (default `DEFAULT_LINE_MARGIN`) y
  `track_timeout_frames` (default `DEFAULT_TRACK_TIMEOUT_FRAMES`) en `CountingLineConfig`,
  con `model_validator` que exige `margin < min(position, 1 - position)`.
- `src/recognizer/core/constants.py`: `DEFAULT_LINE_MARGIN` (0.05) y
  `DEFAULT_TRACK_TIMEOUT_FRAMES` (30).
- `src/recognizer/adapters/overlay_people.py`: dibuja la banda muerta (banda tenue) y
  omite el trazo cuando `margin == 0`.
- `src/recognizer/cli/apps/people_counter.py`: pasa `margin` y `track_timeout_frames` al
  contador.
- `config.yaml`: `people_counter.line.margin` y `track_timeout_frames` documentados y con
  valores por defecto.
- Tests: `tests/unit/test_tracking.py` (migración `side`→`zone`, banda muerta, track que
  nace en banda, jitter, purga por timeout, validación de config) y
  `tests/unit/test_overlay_people.py` (dibujo de la banda).

## Decisiones

- Se mantiene el modelo de "línea + conteo por cruce de track" (una sola vía de
  inferencia). El fix ataca las dos causas reales del descuadre: nacimiento cerca de la
  línea y jitter, más la retención de IDs muertos.
- La banda muerta es hysteresis espacial: el lado solo cambia al superar `position ± margin`,
  de modo que el jitter del centro sobre la línea no alterna de lado. El lado inicial se
  fija de inmediato en el primer fotograma fuera de banda (sin esperar `confirm_frames`),
  porque no es un cruce; `confirm_frames` se reserva a los cambios de lado reales.
- La purga por timeout trata un ID reaparecido como nuevo, evitando que un track muerto
  "resucite" cruzando la línea.
- El conteo perfecto Entradas==Salidas no es alcanzable con una línea (una persona puede
  entrar y salir de cuadro sin cruzar); el fix reduce falsos positivos, no lo garantiza.

## Tests y gate (resultados reales)

- `uv run lint` — OK (183 archivos).
- `uv run typecheck` — OK (158 archivos, mypy strict).
- `uv run test` — **973 passed, 2 deselected**, cobertura **96.75%**
  (`core/domain/tracking.py` y `adapters/overlay_people.py` al 100%).
- `uv run check-arch` — 3/3 contratos KEPT.
- `uv run smoke --frames 30 --no-window` — OK (30 fotogramas, 9.8 FPS, 0 manos).

## Revisión (hallazgos y correcciones)

Apta para merge; 4 hallazgos menores, 3 de código aplicados: guard muerto eliminado en
`tracking.py`; `model_validator` de `margin` en `config.py`; el overlay omite la banda
cuando `margin == 0`. El cuarto (docs) es esta actualización. Sin bloqueantes.

## Commits

- `f5b439c` `fix(10c): banda muerta y purga de tracks en el contador de personas`
- `fed0124` `test(10c): cobertura de banda muerta, purga y config del contador`
- `4e579dc` `docs(10c-fix): history, arquitectura, pending-tests y STATE`
- `40083c2` `merge: 10c-fix — conteo sincronizado (banda muerta + purga)` (en `dev`)

## Pendientes / riesgos

- Calibrar `margin`, `position` y `track_timeout_frames` con cámara real.
- El conteo Entradas==Salidas sigue sin garantizarse con una sola línea (limitación del
  modelo).
