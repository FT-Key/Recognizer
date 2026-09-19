# Etapa 12 — Postura ergonómica (YOLO pose)

- **Rama:** `stage/12-posture`
- **Estado:** completada
- **Objetivo:** app que estima la pose corporal con YOLO pose (una sola vía de
  inferencia, `model.predict`) y avisa de malos hábitos posturales frente a la cámara
  (cabeza adelante, cabeza baja, espalda inclinada y hombros desnivelados).
- **Criterios de aceptación:**
  - [x] Dominio puro `core/domain/pose.py` (`PoseKeypoint`, `COCO_KEYPOINT_ORDER`,
    `Keypoint`, `Pose.keypoint()`) y `core/domain/posture.py` (`PostureIssue`,
    `PostureThresholds`, `PostureAssessment`, `PostureSnapshot`, `assess_posture` y
    `PostureMonitor` con debounce confirm/release).
  - [x] Heurísticos normalizados por la distancia euclídea entre hombros (invariantes a
    la distancia): `max_head_offset_ratio`, `min_head_height_ratio`,
    `max_torso_angle_deg` y `max_shoulder_tilt_ratio`.
  - [x] Puerto `core/ports/pose_estimator.py`; adaptador `adapters/ultralytics_pose.py`
    (fachada inyectable, mapeo `xyn`/`conf`, clamping con guarda de NaN).
  - [x] Overlay `adapters/overlay_posture.py` (esqueleto, HUD y banner de aviso).
  - [x] Runner `cli/apps/posture.py` con alerta sonora opcional (`posture.alert`) y
    salida al menú con `ESC`/`q`.
  - [x] Config `PostureConfig`/`PostureAlertConfig` + defaults en `core/constants.py` +
    sección `posture` en `config.yaml` + `apps.enabled.posture: true`.
  - [x] `AppId.POSTURE` con `implemented=True`; rama perezosa en `cli/menu.resolve_runner`;
    `packaging/recognizer.spec` con hiddenimports de `anti_intruder` y `posture`.
  - [x] Tests sin hardware + gate verde (lint, typecheck, pytest, check-arch, smoke).
  - [x] Revisión independiente apta para merge; menores aplicados; docs/STATE actualizados.

## Plan

1. Dominio: `core/domain/pose.py` y `core/domain/posture.py`.
2. Config: `PostureConfig`/`PostureAlertConfig` + constantes + YAML.
3. Puerto `PoseEstimator` y adaptador `ultralytics_pose`.
4. Overlay, runner, catálogo y menú.
5. Fixes de UI del menú (scroll con rueda y padding).
6. Tests, gate, revisión y docs.

## Cambios (archivos)

Nuevos:
- `src/recognizer/core/domain/pose.py`: `PoseKeypoint` (orden COCO de 17 puntos),
  `COCO_KEYPOINT_ORDER`, `Keypoint` (x/y/confianza validados 0..1) y `Pose.keypoint()`.
- `src/recognizer/core/domain/posture.py`: `PostureIssue`, `PostureThresholds`,
  `PostureAssessment` (`evaluated`/`is_bad`), `PostureSnapshot`, `assess_posture` y
  `PostureMonitor` (debounce `confirm_frames`/`release_frames`; evalúa la persona de
  mayor confianza; los cuadros no evaluables no rompen la racha y liberan si se prolongan).
- `src/recognizer/core/ports/pose_estimator.py`: `PoseEstimatorConfig` estructural
  (`model_path`, `min_confidence`) y puerto `PoseEstimator` (`open`/`estimate`/`close`).
- `src/recognizer/adapters/ultralytics_pose.py`: `UltralyticsPoseEstimator` sobre
  `model.predict` de `yolo26n-pose.pt` (se descarga solo); fachada inyectable para tests,
  mapeo `xyn`/`conf` y clamping con guarda de NaN.
- `src/recognizer/adapters/overlay_posture.py`: `draw_posture_overlay` (esqueleto, HUD de
  avisos y banner; el color de aviso también tiñe los puntos del esqueleto).
- `src/recognizer/cli/apps/posture.py`: runner `run_posture`; alerta edge-triggered con
  repetición según `posture.alert.repeat_seconds`; `ESC`/`q` vuelve al menú.
- Tests: `tests/unit/test_pose.py`, `test_posture.py`, `test_ultralytics_pose.py`,
  `test_overlay_posture.py`.

Modificados:
- `src/recognizer/core/config.py`: `PostureAlertConfig`, `PostureConfig` y
  `AppConfig.posture`.
- `src/recognizer/core/constants.py`: defaults `DEFAULT_POSTURE_*`.
- `src/recognizer/core/errors.py`: `PoseEstimatorError`.
- `src/recognizer/core/domain/app.py`: `posture` con `implemented=True`.
- `src/recognizer/cli/menu.py`: rama `AppId.POSTURE` con import perezoso.
- `src/recognizer/cli/menu_gui.py`: scroll con la rueda sobre cualquier opción (binding
  `<MouseWheel>` en la raíz vía `_scroll_canvas`, con `WHEEL_DELTA`) y padding del badge
  de estado y de las filas.
- `config.yaml`: sección `posture` (modelo, umbrales, debounce y alerta) +
  `apps.enabled.posture: true`; cámara a 1280x720.
- `packaging/recognizer.spec`: hiddenimports de `anti_intruder` y `posture`.
- `tests/unit/test_app_domain.py`, `test_menu.py`, `test_menu_gui.py`: POSTURE ahora
  disponible; los casos coming-soon/disabled pasan a `PPE_DETECTOR`.

## Decisiones

- Una sola vía de inferencia: `model.predict` de YOLO pose (sin detector de respaldo que
  reprocese el fotograma).
- Heurísticos normalizados por la distancia euclídea entre hombros: invariantes a la
  distancia a la cámara y robustos a vista girada.
- Debounce de confirmación/liberación; los cuadros no evaluables no resetean la racha y
  liberan el aviso si se prolongan (no dejar la alerta colgada al salir del encuadre).
- Cámara a 1280x720: la ventana de cada app muestra el fotograma a su resolución nativa.
  En esta CPU el smoke pasa de 11.8 FPS (640x480) a 9.7 FPS (1280x720) con MediaPipe; se
  acepta el trade-off por una imagen más grande y es reversible bajando `width`/`height`.
- El aviso "cabeza adelante" solo mide desvío horizontal en 2D (limitación conocida).

## Tests y gate (resultados reales)

- `uv run lint` — OK.
- `uv run typecheck` — OK (158 archivos, mypy strict).
- `uv run test` — **904 passed**, cobertura **96.76%**.
- `uv run check-arch` — 3/3 KEPT.
- `uv run smoke --frames 30 --no-window` — OK (30 fotogramas, 9.7 FPS a 1280x720, 0 manos).

## Revisión (hallazgos y correcciones)

Apta para merge. Menores aplicados: guarda de NaN en el clamping; ancho de hombros
euclídeo; debounce que no resetea la racha por cuadros no evaluables y libera si se
prolongan; uso real de `WHEEL_DELTA`; color de aviso también en los puntos del esqueleto.
Menor no aplicado y aceptado: `alert.close()` se hace por `ExitStack` y por `finally`
(idempotente, mismo patrón que anti-intrusos).

## Commits

Cambios de la etapa en el árbol de trabajo sobre `stage/12-posture` (HEAD en `ab59b05`,
merge de 11); pendientes de commit al cierre.

## Pendientes / riesgos

- Calibrar con cámara real los umbrales de postura (`max_head_offset_ratio`,
  `min_head_height_ratio`, `max_torso_angle_deg`, `max_shoulder_tilt_ratio`,
  `confirm_frames`/`release_frames`).
- El aviso "cabeza adelante" solo mide desvío horizontal en 2D.
- Verificación del `.exe` con YOLO pose pendiente (bundle pesado).
- Los `.md` `docs/DESKTOP-EXPLICADO.md` y `docs/DESKTOP-SIMPLIFICADO.md` quedan sin
  trackear (ajenos a la etapa).
