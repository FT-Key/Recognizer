# Etapa 5 — Gestos personalizados (vocabulario abierto y reglas)

- **Rama:** stage/5-gestos-personalizados
- **Estado:** completada
- **Objetivo:** abrir el vocabulario de gestos (más allá de los 7 canned) y permitir
  definir gestos personalizados en `config.yaml` por reglas geométricas de landmarks y
  por etiquetas de un modelo MediaPipe custom, pudiendo mapearles acciones.

- **Criterios de aceptación:**
  - El vocabulario de gestos es abierto: `GestureId` (value object) reemplaza al enum
    cerrado `GestureName`; los 7 gestos canned siguen funcionando igual. ✅
  - `GestureCatalog` = canned + `gestures.custom_labels` + nombres de reglas; valida de
    forma fail-fast mapeos y gestos de activación del puntero. ✅
  - Reglas de landmarks definidas en `config.yaml` (dedos extendidos/doblados, ángulo
    entre dedos, dirección) generan `DetectedGesture` mapeables a acciones. ✅
  - Un modelo MediaPipe custom (`.task` de Model Maker) puede emitir etiquetas declaradas
    en `custom_labels` y son reconocidas por el pipeline. ✅
  - `config.yaml`, README, ARCHITECTURE y tests actualizados; gate verde. ✅

## Plan
1. Vocabulario abierto: `GestureId` + constantes, migración de core/adapters.
2. Catálogo + esquema de config (`custom_labels`, `rules`, `rule_thresholds`, prioridad).
3. Adaptador MediaPipe: etiquetas custom filtradas por catálogo.
4. Motor de reglas de landmarks + `LandmarkRuleProcessor` + wiring.
5. `config.yaml` de ejemplo (reglas `One_Finger_Up` y `L_Sign`, comentadas).
6. Tests actualizados y nuevos; gate.

## Cambios (archivos)
- `core/domain/gesture.py`: `GestureId` (value object frozen), constantes `GESTURE_*`,
  `CANNED_GESTURES`/`CANNED_GESTURE_LABELS`, enums `Finger`/`Direction8`/`RulesPriority` y
  `GestureCatalog` (`resolve`/`require`/`is_known`/`from_labels`).
- `core/domain/hand.py`: índices de los 21 landmarks (MCP/PIP/DIP/TIP por dedo).
- `core/domain/events.py`: `GestureDetected`/`GestureReleased` con `GestureId`.
- `core/config.py`: `custom_labels`, `rules`, `rules_priority`, `rule_thresholds`;
  `RuleThresholdsConfig`, `DirectionConditionConfig`, `AngleConditionConfig`,
  `GestureRuleConfig`; `ActionsConfig.mappings: dict[str, ActionConfig]`;
  `PointerConfig.activation_gesture: str`; validación de catálogo en `AppConfig`.
- `core/constants.py`: `RULE_CONFIDENCE`, `MIN_VECTOR_NORM`, umbrales por defecto.
- `core/pipeline/landmark_rules.py` (nuevo): geometría de manos (`is_finger_extended`,
  `finger_direction`, `matches_direction`, `matches_angle`), `LandmarkRule`,
  `evaluate_rule`/`match_rules` y `LandmarkRuleProcessor` (prioridad reglas/modelo).
- `core/pipeline/{gesture_stabilization,pointer_detection}.py`,
  `core/actions/dispatcher.py`, `cli/{app,smoke}.py`: migrados a `GestureId` (comparación
  por igualdad).
- `adapters/mediapipe_gesture_classifier.py`: etiquetas permitidas canned ∪ `custom_labels`;
  `None`/`Unknown`/no declaradas → `GESTURE_NONE`.
- `bootstrap.py`: catálogo único y `LandmarkRuleProcessor` entre detección y estabilizador.
- `config.yaml`: `custom_labels`, `rules_priority`, `rule_thresholds` y ejemplos comentados.

## Decisiones
- Se soportan **dos** fuentes de gestos personalizados: modelo custom y reglas de
  landmarks, por ser lo más escalable y no obligar a entrenar para probar.
- Dirección v1 = pose estática (dedo/mano); el swipe temporal queda como extensión.
- `custom_labels` es allowlist explícita: lo no declarado se descarta (evita ruido).
- `rules_priority=rules_first` por defecto; usar `model_first` si una regla coincide con
  el gesto del puntero (`Pointing_Up`) para no desactivarlo.
- Compatibilidad total con los 7 gestos y el `config.yaml` previo (reglas vacías por
  defecto).

## Tests y gate (resultados reales)
- `uv run test`: **342 passed**, 2 deselected, cobertura **98.72%** (umbral 80%).
- `uv run pytest -m integration --no-cov`: **2 passed**, 340 deselected.
- `uv run lint`: ruff check OK; ruff format OK (87 archivos src/tests).
- `uv run typecheck`: mypy strict OK (87 archivos).
- `uv run check-arch`: **3/3** contratos KEPT.
- `uv run smoke --frames 30 --no-window`: **Smoke OK**, 30 fotogramas, 13.7 FPS.
- Tests nuevos: `test_gesture_catalog.py`, `test_landmark_rules.py`,
  `test_gesture_rules_config.py`; casos de etiqueta custom en
  `test_mediapipe_gesture_classifier.py`. Tests actualizados (17) por el cambio a
  `GestureId` y firmas de config/bootstrap.

## Revisión (hallazgos y correcciones)
- Revisión independiente sin hallazgos bloqueantes ni mayores; 2 menores corregidos:
  (1) mano degenerada (todos los puntos colapsados) ya no produce falsos positivos por
  `atan2(0,0)`/dedos doblados — `evaluate_rule` rechaza manos sin dispersion respecto a
  la muñeca; (2) `is_finger_extended`/`finger_direction`/`matches_direction`/`matches_angle`
  validan la longitud (21 landmarks) con `ValueError` en vez de `IndexError`. Tests
  anadidos para ambos.

## Commits
_(pendiente)_

## Pendientes / riesgos
- Verificar en uso real que un bundle custom de Model Maker carga con `model_asset_path`
  (canned + custom en un solo `.task`); falta un modelo custom de prueba.
- `One_Finger_Up` (regla) compite con `Pointing_Up` del puntero; documentado el uso de
  `model_first`.
