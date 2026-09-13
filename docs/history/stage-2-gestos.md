# Etapa 2 — Gestos: clasificador, estabilizador y overlay

- **Rama:** stage/2-gestos
- **Estado:** completada
- **Objetivo:** Clasificar gestos predefinidos por mano con MediaPipe GestureRecognizer,
  confirmarlos tras N frames estables (anti-parpadeo), publicar eventos tipados y
  mostrarlos en el overlay del smoke.
- **Criterios de aceptación:**
  - Un gesto solo se confirma tras `stabilization_frames` frames consecutivos con el mismo
    resultado; se libera tras `release_frames` frames sin observarlo.
  - Eventos `GestureDetected` / `GestureReleased` edge-triggered, sin duplicados por frame.
  - Puerto `GestureClassifier` (Strategy) + adaptador `MediaPipeGestureClassifier` con
    fachada inyectable; el smoke usa el modelo de gestos por defecto (`--no-hands` = base).
  - Overlay muestra el gesto confirmado por mano.
  - Smoke real: mostrar `Victory` y `Open_Palm` -> al menos 1 `GestureDetected` de cada uno
    — **PENDIENTE** de verificación manual; decisión del usuario: mergear con el criterio
    pendiente.
  - Sin regresión de FPS respecto de la etapa 1 en igualdad de carga.
  - Gate verde: lint, typecheck, test (cobertura >= 80%) y check-arch.

## Plan
1. Core: dominio (`GestureName`, `DetectedGesture`, `StableGesture`, `GestureRecognition`),
   eventos (`GestureDetected`, `GestureReleased`), puerto `GestureClassifier`.
2. Config: `GestureConfig` en `core/config.py`, defaults en `core/constants.py` y sección
   `gestures` en `config.yaml`.
3. Adaptador `MediaPipeGestureClassifier` (GestureRecognizer en modo VIDEO, un solo pase:
   landmarks + lateralidad + gesto; fachada inyectable, import perezoso).
4. Pipeline: `GestureDetectionProcessor` y `GestureStabilizerProcessor`; `FrameContext`
   gana `detections` y `gestures`.
5. Overlay `GestureOverlay` y smoke con contador `match/case` de ambos eventos.
6. Tests unitarios (landmarks/fachadas sinteticos) e integración MediaPipe.
7. Gate, revisión independiente y cierre; verificar también el FPS pendiente de la etapa 1.

## Cambios (archivos)
- `src/recognizer/core/domain/gesture.py` (nuevo): `GestureName`, `DetectedGesture`,
  `StableGesture` y `GestureRecognition` (manos y detecciones paralelas por indice).
- `src/recognizer/core/ports/gesture_classifier.py` (nuevo): puerto `GestureClassifier`
  (`open`/`classify`/`close`) con el invariante de timestamp monotono documentado.
- `src/recognizer/core/pipeline/gesture_detection.py` (nuevo): `GestureDetectionProcessor`
  (clasifica, publica `HandsDetected` y anota manos/detecciones).
- `src/recognizer/core/pipeline/gesture_stabilization.py` (nuevo):
  `GestureStabilizerProcessor` (confirmacion por N frames, liberacion por M ausencias).
- `src/recognizer/adapters/mediapipe_gesture_classifier.py` (nuevo):
  `MediaPipeGestureClassifier` y fachada inyectable `MediaPipeTasksGestureFacade`
  (GestureRecognizer en modo VIDEO, import perezoso, errores envueltos).
- `src/recognizer/core/domain/events.py`: `GestureDetected` y `GestureReleased`.
- `src/recognizer/core/pipeline/context.py`: campos `detections` y `gestures`.
- `src/recognizer/core/constants.py`, `core/config.py` (`GestureConfig`), `core/errors.py`
  (`GestureClassifierError`) y `config.yaml` (seccion `gestures`): actualizados.
- `src/recognizer/adapters/overlay_opencv.py`: `GestureOverlay` sobre la muneca;
  `LandmarkOverlay` intacto.
- `src/recognizer/cli/smoke.py`: clasificador de gestos por defecto, pipeline
  deteccion -> estabilizacion -> overlays, `_GestureStats` con `match/case` y log final
  con maximo de manos y gestos confirmados.

## Decisiones
- Un solo modelo (`gesture_recognizer.task`) hace landmarks, lateralidad y gestos en un
  pase; el smoke deja de usar `HandLandmarker`, que se conserva intacto para su puerto.
- El puerto `GestureClassifier` sigue Strategy: permite cambiar de motor de clasificacion
  (modelo propio, web) sin tocar processors ni overlay.
- Estabilizacion edge-triggered con estado independiente por lateralidad LEFT/RIGHT:
  `GestureDetected`/`GestureReleased` solo se publican al cambiar de estado confirmado;
  al confirmar un gesto nuevo se emite primero el release del anterior.
- `Handedness.UNKNOWN` se ignora para no mezclar el estado de dos manos sin lateralidad.
- `min_gesture_confidence` filtra observaciones antes de acumular estabilidad y el gesto
  `None` del modelo nunca se confirma.
- Helpers de imagen y landmarks duplicados a proposito en el adaptador de gestos: evita
  acoplar dos adaptadores por un codigo pequeno y estable.
- El y-offset del gesto en el overlay se satura a 0 para no dibujar fuera del fotograma.

## Tests y gate (resultados reales)
- `uv run lint`: OK (ruff check + format, 71 archivos).
- `uv run typecheck`: OK (mypy strict, 48 archivos).
- `uv run test`: 135 passed + 2 deselected, cobertura 97.95% (umbral 80%).
- `uv run check-arch`: 3/3 contratos KEPT.
- Integración real: `pytest -m integration` con el `GestureRecognizer` de MediaPipe OK.
- `uv run smoke --frames 30 --no-window`: OK real (cámara + modelo de gestos, 30 eventos
  `HandsDetected`).

### Rendimiento medido (pendiente)
- Smoke con modelo de gestos: 8.2 FPS con CPU al 39-87% por carga externa (Chrome, VS Code,
  TeamViewer, opencode) y sin manos en cámara; etapa 1 bajo condiciones similares: 9.3 FPS.
- Criterio "2 manos + `Victory`/`Open_Palm`" **PENDIENTE** de verificación manual en equipo
  descargado (`uv run smoke --frames 180` mostrando cada gesto); decisión del usuario:
  mergear con el criterio pendiente.
- El FPS pendiente de la etapa 1 sigue sin verificar.

## Revisión (hallazgos y correcciones)
- Veredicto del `reviewer`: "apto para merge" condicionado a la verificación manual y al
  registro del gate.
- 3 hallazgos corregidos: (a) al liberar un gesto ya no se reinicia el candidato en curso
  (`release_frames < stabilization_frames` confirma sin reiniciar el conteo); (b) ante dos
  detecciones de la misma lateralidad gana la de mayor confianza; (c) tests de borde añadidos
  (release<N, candidato revertido, empate de confianza) y del wiring del smoke.
- Nit: el overlay usa `GESTURE_COLOR_BGR` (naming, no defecto); secciones del history (esto).

## Commits
- Pendiente de registrar: commit de cierre en `stage/2-gestos` y merge `--no-ff` a `dev`.

## Pendientes / riesgos
- Verificación manual de `Victory`/`Open_Palm` y FPS en equipo descargado (etapas 1-2).
- Si en equipos débiles el FPS sigue bajo, la etapa 3/4 podrá evaluar decimación de detección
  o inferencia asíncrona.
- `opencode`/apps externas compiten por CPU en las pruebas.
