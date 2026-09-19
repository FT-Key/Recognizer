# Estado — Recognizer

- **Fase actual:** etapa 12 (postura con YOLO pose) + fix 12b completadas; siguiente: 13 (Detector EPP de obra, requiere entrenamiento)
- **Rama:** `stage/12b-posture-fix` (12 mergeada a `dev` en `4304ec2`)
- **Actualizado:** 2026-09-18

## Hecho
- Repo `FT-Key/Recognizer` (`main`/`dev`); uv + Python 3.12; deps (+`ultralytics`).
- Core base (`Frame`, puertos, config, errores), `OpenCVCamera`, CLI `smoke`.
- Etapas 1-2: manos (MediaPipe + `EventBus`) y gestos + estabilizador + overlay.
- Etapa 3: acciones locales (media/hotkey/command/script) con dispatcher + HUD.
- Etapa 4: puntero virtual (suavizado ema, zona 0.2-0.8, `MouseController`).
- Etapa 5: gestos personalizados (reglas de landmarks en `config.yaml`).
- Etapa 6: acciones script (`.py/.ps1/.bat/.cmd/.sh`, `RECOGNIZER_*` opt-in).
- Etapa 7: `open_links` + ejemplo `scripts/actions/log_gesture.py`.
- Etapa 8: menús compuestos por mano + `gestures.swap_handedness`.
- Etapa 9: web React 19 + Vite (Vercel) y `.exe` PyInstaller + `/health`.
- Etapas 9b-9c: navegador CDP (`open_tab`/`tab_seek`/`tab_press`), fix Chrome 152 y scroll con `Victory`/`Closed_Fist` + mute.
- Etapa 10a: launcher multi-app (menú, import perezoso, `ESC`/`q`); merge `c8c8b9f`.
- Etapa 10b: contador YOLO (`yolo26n.pt` nano CPU); dominio + puerto + `UltralyticsDetector` + runner HUD `Personas: N`; `.spec` sin torch.
- Etapa 10b-fix: salida ESC/q+X a menú (topmost + `WND_PROP_VISIBLE`, tolerante a `cv2.error`); menú tkinter/ttk perezoso (`menu_gui`) + `--no-gui`/fallback `TclError`.
- Etapa 10d: rediseño UX/UI vintage del menú (`MenuTheme`, botones, badges, logo e icono, fuente pixel Silkscreen en `assets/`); `paths.py` resuelve assets (`_MEIPASS`).
- Etapa 10c: tracking YOLO (`model.track`, ByteTrack `persist=True`), dominio `core/domain/tracking.py`, puerto `ObjectTracker`, overlay `overlay_people.py` y `people_counter.line`; runner HUD Personas/Entradas/Salidas.
- Etapa 11: anti-intrusos; dominio `core/domain/intrusion.py`, puerto `AlertSink`, adaptadores `alert_sound`/`overlay_intrusion` y runner `cli/apps/anti_intruder.py`; zona + alerta sonora edge-triggered.
- Etapa 12: postura con YOLO pose (una sola vía: `model.predict` de `yolo26n-pose.pt`, se descarga solo); dominio `core/domain/pose.py` + `posture.py` (`assess_posture`/`PostureMonitor`, heurísticos normalizados por ancho de hombros), puerto `pose_estimator`, adaptador `ultralytics_pose`, overlay `overlay_posture` y runner `cli/apps/posture.py`; `AppId.POSTURE` `implemented=True`.
- Fixes de menú (12): rueda sobre cualquier opción (`<MouseWheel>` en la raíz, `WHEEL_DELTA`) y padding de badge/filas; cámara a 1280x720 (trade-off de FPS registrado).
- Gate 12 verde: pytest **904 passed** (96.76%), mypy strict 158 archivos, ruff, check-arch 3/3, smoke 9.7 FPS (1280x720). Reviewer: apta para merge (menores aplicados).
- Fix 12b: `measure_posture` con medición parcial (métricas que pueden faltar; escala por hombros/torso/cabeza; un solo hombro/cadera) y calibración en `PostureMonitor` (`calibration_frames` + `tolerances`, mediana de la postura correcta); `PostureSnapshot.calibrating` + HUD "Calibrando"; debounce tolerante a fotogramas no evaluables.
- Gate 12b verde: pytest **946 passed** (96.67%), mypy strict 158 archivos, ruff, check-arch 3/3; app de postura headless EXIT 0 con modelo real. Reviewer: apta para merge (menores aplicados).

## Siguiente (etapa 13 — Detector EPP de obra)
- Requiere entrenamiento (EPP/cascos/chalecos). Roadmap: 14 inventario, 15 facial (checklist en `docs/WORKFLOW.md`, skill `new-app`).

## Bloqueos / notas
- Usuario verifica manual: ESC/q+X, ventana del menú con cámara real y **aspecto visual del rediseño 10d**.
- Verificación del `.exe` con YOLO/torch y con YOLO pose pendiente (bundle ~1 GB, excluido); regenerar `.exe` para probar assets/icono.
- Calibrar con cámara real: `posture.calibration_frames` y `posture.tolerances` (o los umbrales absolutos si `calibration_frames: 0`), `anti_intruder.zone` y `alert.repeat_seconds`, `people_counter.line`, `min_confidence` y `swap_handedness`.
- "Cabeza adelante" solo mide desvío horizontal en 2D (limitación conocida).
- `PENDING-TESTS.md`: verificaciones manuales de etapas 0-9b las hace el usuario.
- Tras editar `opencode.json`/agentes/skills/comandos: reiniciar opencode.
