# Etapa 12b — Fix postura: medición parcial y calibración

- **Rama:** `stage/12b-posture-fix`
- **Estado:** completada
- **Objetivo:** corregir que la app de postura de la etapa 12 nunca evaluara la pose
  (siempre "Postura OK") y hacer la medición robusta a oclusiones (caderas ocultas al
  sentarse, perfil con un hombro perdido) y a la cámara/usuario mediante calibración.
- **Criterios de aceptación:**
  - [x] `measure_posture` calcula métricas de forma parcial: cada una
    (`head_offset_ratio`, `head_height_ratio`, `torso_angle_deg`, `shoulder_tilt_ratio`)
    puede faltar sin invalidar el resto; acepta un solo hombro/cadera visible.
  - [x] Escala corporal robusta (ancho de hombros; en perfil largo del torso; si no hay
    caderas ni par de hombros, tamaño de cabeza por orejas).
  - [x] `PostureMonitor` calibra durante `calibration_frames` fotogramas evaluables
    (mediana por métrica) y avisa cuando una métrica se desvía más de `tolerances`;
    `calibration_frames: 0` usa umbrales absolutos.
  - [x] `PostureSnapshot.calibrating`; runner y overlay muestran "Calibrando" sin alertar.
  - [x] Config `PostureConfig.calibration_frames` + `tolerances` y `config.yaml`
    documentado (sentarse derecho al inicio).
  - [x] Debounce tolerante a fotogramas no evaluables y sin contar como buena una
    métrica ausente.
  - [x] Tests sin hardware + gate verde (lint, typecheck, pytest, check-arch).
  - [x] Revisión independiente apta para merge; menores aplicados; docs/STATE actualizados.

## Plan

1. Diagnóstico: por qué `assess_posture` nunca evaluaba (nariz + ambos hombros + ambas
   caderas obligatorios) y por qué los umbrales absolutos eran frágiles.
2. Dominio: `measure_posture` (métricas parciales) y escala corporal robusta.
3. Dominio: calibración en `PostureMonitor` (línea base por mediana + tolerancias).
4. Runner y overlay: estado `calibrating` sin alerta.
5. Config: `calibration_frames`/`tolerances`, constantes y YAML.
6. Tests, gate, revisión y docs.

## Cambios (archivos)

Modificados:
- `src/recognizer/core/domain/posture.py`: `measure_posture` y `PostureMetrics`
  (métricas opcionales por métrica); `_body_scale` (ancho de hombros, largo del torso en
  perfil, ancho de cabeza por orejas como último recurso); `PostureTolerances`,
  `PostureBaseline` y `_compute_baseline` (mediana); `PostureMonitor` con
  `calibration_frames`/`tolerances`, propiedad `calibrating`, recolección de calibración y
  evaluación por desvío; `PostureSnapshot.calibrating`; debounce que no rompe la racha por
  un fotograma no evaluable y que no cuenta como buena una métrica ausente.
  `assess_posture`/`PostureAssessment` se mantienen como API de umbrales absolutos.
- `src/recognizer/cli/apps/posture.py`: construye `PostureTolerances`, pasa
  `calibration_frames`/`tolerances`; no alerta mientras calibra y muestra HUD/log
  "Calibrando (sientate derecho)".
- `src/recognizer/adapters/overlay_posture.py`: banner "CALIBRANDO: sientate derecho".
- `src/recognizer/core/config.py`: `PostureTolerancesConfig` y campos
  `calibration_frames`/`tolerances` en `PostureConfig`.
- `src/recognizer/core/constants.py`: `DEFAULT_POSTURE_CALIBRATION_FRAMES`,
  `DEFAULT_POSTURE_TOLERANCE_*`, `POSTURE_PROFILE_SHOULDER_RATIO` y umbrales absolutos más
  sensibles (`min_head_height_ratio` 0.7, `max_torso_angle_deg` 15.0,
  `max_shoulder_tilt_ratio` 0.15).
- `config.yaml`: flujo de calibración documentado y tolerancias por defecto.
- Tests: `tests/unit/test_posture.py`, `test_pose.py`, `test_overlay_posture.py`.

## Decisiones

- Medición parcial en lugar de exigir los 5 puntos: al sentarse las caderas quedan ocultas
  por el escritorio (baja confianza) y en perfil se pierde un hombro; exigirlos hacía que
  la app no evaluara nunca.
- Escala corporal robusta por contexto (hombros/torso/cabeza) para normalizar las métricas
  sin depender de la distancia a la cámara.
- Calibración como vía principal: aprende la postura correcta al inicio y avisa por desvío,
  más robusta que umbrales absolutos ante cámara/usuario; los absolutos quedan como
  fallback (`calibration_frames: 0`).

## Tests y gate (resultados reales)

- `uv run lint` — OK.
- `uv run typecheck` — OK (158 archivos, mypy strict).
- `uv run test` — **946 passed, 2 deselected**, cobertura **96.67%**.
- `uv run check-arch` — 3/3 KEPT.
- App de postura headless (`run_posture` con `show_window=False, max_frames=30`) — EXIT 0
  con el modelo pose real.
- `uv run smoke` no se ejecutó en esta etapa: la app de gestos no cambia y el smoke de la
  etapa 12 ya estaba verde.

## Revisión (hallazgos y correcciones)

Apta para merge. Aplicados: no contar como postura correcta un fotograma sin la métrica que
disparó el aviso (fix de parpadeo con métricas parciales) y tests del fallback de escala por
cabeza. Menores no aplicados y aceptados: tolerancias absolutas vs escala-cabeza (en perfil
puede ser más sensible, caso poco frecuente) y `assess_posture`/`PostureAssessment` quedan
como API de umbrales absolutos usada por tests.

## Commits

Cambios de la etapa en el árbol de trabajo sobre `stage/12b-posture-fix` (HEAD en
`4304ec2`, merge de 12 a `dev`); pendientes de commit al cierre.

## Pendientes / riesgos

- Calibrar `posture.tolerances` y `posture.calibration_frames` con la cámara real del
  usuario.
- "Cabeza adelante" solo mide desvío horizontal en 2D (limitación conocida; la calibración
  la mitiga en parte).
- Verificación del `.exe` con YOLO pose pendiente (bundle pesado).
- Los `.md` `docs/DESKTOP-EXPLICADO.md` y `docs/DESKTOP-SIMPLIFICADO.md` siguen sin
  trackear (ajenos a esta etapa).
