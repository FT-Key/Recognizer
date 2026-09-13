# Etapa 1 — Manos: HandLandmarker, EventBus y overlay

- **Rama:** stage/1-manos
- **Estado:** completada
- **Objetivo:** Detectar hasta 2 manos por fotograma con MediaPipe Tasks (CPU), publicar
  eventos tipados in-process y dibujar los 21 landmarks sobre la ventana del smoke.
- **Criterios de aceptación:**
  - Puerto `HandTracker` + adaptador `MediaPipeHandTracker` con fachada inyectable;
    tests unitarios con dobles, sin hardware.
  - `EventBus` tipado in-process: eventos `frozen=True`, despacho con `match/case`, sin `Any`.
  - `PipelineBuilder` + processors `HandDetectionProcessor` y overlay OpenCV.
  - Smoke con overlay de 21 landmarks y flag `--no-hands` para comparar contra la base.
  - Criterio físico: 2 manos a 640x480 con >= 20 FPS en CPU (smoke real, verificación manual) —
    **PENDIENTE** de verificación; decisión del usuario: mergear con el criterio pendiente.
  - Gate verde: lint, typecheck, test (cobertura >= 80%), check-arch y smoke.

## Plan
1. Core: dominio (`Handedness`, `Point`, `HandLandmarks`), eventos (`HandsDetected`),
   puertos (`HandTracker`, `EventBus`), bus in-process y pipeline (`FrameContext`,
   `Processor`, `PipelineBuilder`, `HandDetectionProcessor`).
2. Config: `HandsConfig` en `core/config.py`, defaults en `core/constants.py` y sección
   `hands` en `config.yaml`.
3. Adaptadores: `MediaPipeHandTracker` (MediaPipe Tasks, modo VIDEO, fachada inyectable)
   y overlay OpenCV de landmarks.
4. CLI `smoke`: pipeline, suscripción al bus con `match/case`, flag `--no-hands` y log
   del máximo de manos detectadas.
5. Tests unitarios con landmarks sintéticos y dobles; smoke real de FPS.
6. Gate, revisión independiente y cierre.

## Cambios (archivos)
- `src/recognizer/core/domain/hand.py` (nuevo): `Handedness`, `Point`, `HandLandmarks`,
  `HAND_LANDMARK_COUNT` y `HAND_CONNECTIONS`.
- `src/recognizer/core/domain/events.py` (nuevo): `DomainEvent` y `HandsDetected`.
- `src/recognizer/core/ports/hand_tracker.py` (nuevo): puerto `HandTracker`.
- `src/recognizer/core/ports/event_bus.py` (nuevo): puerto `EventBus` tipado.
- `src/recognizer/core/bus.py` (nuevo): `InProcessEventBus`.
- `src/recognizer/core/pipeline/` (nuevo): `FrameContext`, `Processor`, `Pipeline`,
  `PipelineBuilder` y `HandDetectionProcessor`.
- `src/recognizer/core/constants.py`, `core/config.py` (`HandsConfig`), `core/errors.py`
  (`HandTrackerError`) y `config.yaml` (seccion `hands`): actualizados.
- `src/recognizer/adapters/mediapipe_hand_tracker.py` (nuevo): `MediaPipeHandTracker` y
  fachada `MediaPipeTasksFacade`.
- `src/recognizer/adapters/overlay_opencv.py` (nuevo): `LandmarkOverlay`.
- `src/recognizer/cli/smoke.py`: pipeline, suscripcion al bus, flag `--no-hands` y log del
  maximo de manos.

## Decisiones
- `HandsDetected` se publica en cada fotograma, incluso sin manos: mantiene el stream de
  eventos completo para estabilizadores/acciones y evita estados "sin evento".
- El bus vive en `core/bus.py` (in-process, sincrono, sin broker externo): cumple Observer
  y la regla de admision sin dependencias de infraestructura.
- `mediapipe` se importa de forma perezosa dentro de la fachada: importar el adaptador (o el
  core) no carga el runtime ni exige el modelo.
- `HandDetectorFacade` es inyectable en `MediaPipeHandTracker` via `facade_factory`: es el
  punto de doble para tests sin MediaPipe ni hardware.
- `HAND_LANDMARK_COUNT` vive solo en `core/domain/hand.py`, junto a `HAND_CONNECTIONS`.
- `Handedness` hereda de `StrEnum` (no de `str, Enum`) para que ruff (`UP042`) pase; los
  valores y el uso via `.value` no cambian.
## Tests y gate (resultados reales)
- `uv run lint`: OK (ruff check + format, 60 archivos).
- `uv run typecheck`: OK (mypy strict, 38 archivos).
- `uv run test`: 75 passed + 1 deselected, cobertura 98.01% (umbral 80%).
- `uv run check-arch`: 3/3 contratos KEPT.
- Integración: `pytest -m integration` (MediaPipe real) 1 passed.
- `uv run smoke --frames 30 --no-window`: OK real (cámara + modelo + 30 eventos `HandsDetected`).

### Rendimiento medido (pendiente)
- Máquina: AMD Ryzen 3 3200G (4c/4t) con CPU al 83-94% por carga externa (Chrome, VS Code,
  TeamViewer, opencode).
- Smoke con pipeline de manos: 9.3 FPS; sin manos (`--no-hands`): 25.1 FPS; detección pura
  aislada: 62-72 ms/frame (13.8-16.2 FPS). Base etapa 0: 29.3 FPS.
- Criterio "2 manos a 640x480 >= 20 FPS" **PENDIENTE** de verificación manual en equipo
  descargado (`uv run smoke --frames 120 --no-window` con 2 manos); decisión del usuario:
  mergear la etapa con el criterio pendiente.

## Revisión (hallazgos y correcciones)
- Veredicto del `reviewer`: "no apto para merge" únicamente por el criterio físico pendiente;
  sin hallazgos bloqueantes de código.
- 3 hallazgos menores corregidos: (a) `detect` envuelve fallos de MediaPipe/cv2 en
  `HandTrackerError`; (b) `--no-window` exige `--frames > 0`; (c) invariante de timestamp
  monótono documentado en el puerto `HandTracker`.
- 2 nits corregidos: `WRIST_LANDMARK_INDEX` y secciones del history.

## Commits
- Los cambios de la etapa (documentación incluida) se cierran con commit en `stage/1-manos`;
  `git-ops` ejecuta a continuación el merge `--no-ff` a `dev` y el push. Base de la rama:
  `95e277b` (`docs(state): etapa 0 publicada en dev y hashes registrados`).

## Pendientes / riesgos
- Criterio FPS sin verificar (ver arriba).
- En etapa 2 el `GestureStabilizer` podrá absorber decimación de detección si el FPS sigue
  bajo en equipos débiles.
- `opencode`/apps externas compiten por CPU en las pruebas.
