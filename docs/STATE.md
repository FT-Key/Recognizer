# Estado — Recognizer

- **Fase actual:** etapa 15b (roles/permisos sobre login facial) completada; siguiente: 13 (EPP, requiere entrenamiento) o 15c (DB distribuida)
- **Rama:** `stage/15b-face-roles` (merge pendiente de `git-ops`)
- **Actualizado:** 2026-09-19

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
- Fix 10c-fix (contador): `CountingLine` con banda muerta `margin` (hysteresis, `zone()` sustituye a `side()`, `SIDE_UNKNOWN` en banda) y `LineCrossingCounter` con lado inicial inmediato, `confirm_frames` solo en cambios de lado y purga `track_timeout_frames`; overlay dibuja la banda; config `people_counter.line.margin` (0.05) y `track_timeout_frames` (30).
- Gate 10c-fix verde: pytest **973 passed** (96.75%), mypy strict 158 archivos, ruff, check-arch 3/3; `tracking.py` y `overlay_people.py` al 100%. Reviewer: apta para merge (menores aplicados).
- Fix 10c-fix2 (contador): eje `vertical` por defecto en `people_counter.line` (paso lateral izquierda derecha = entradas; con `invert` se intercambian); el eje horizontal sigue con `axis: horizontal`.
- Etapa 15a: enrolamiento + login facial con archivos locales (`data/faces/`, ID secuencial F-0001 en `index.json`); `FaceRepository` como seam para DB futura; InsightFace `buffalo_s` CPU una sola vía, 5 ángulos + distancia 0.25-0.55, login con debounce; `AppId.FACE_AUTH` `implemented=True`.
- Gate 15a verde: pytest **1033 passed** (94.63%), mypy strict 169 archivos, ruff, check-arch 3/3; facial `[disponible]`. Reviewer: apta para merge (mayores corregidos: path-traversal + chmod 0700). Commits pendientes `git-ops`.
- Etapa 15b: roles `admin > operator > viewer` sobre login 15a (`core/domain/identity.py` + `PolicyEngine`, puerto `IdentityProvider`, `FileIdentityProvider` con sesión `session.json` + expiración); `EnrolledFace.role` + migración legado→operator (primer usuario→admin, inválido→viewer); enroll/login/logout con rol; menú (`menu.py`/`menu_gui.py`) filtra por rol y revalida al clic; `FaceAuthConfig` (`require_login: false` por defecto, invitado viewer) + `AuthError`.
- Gate 15b verde: pytest **1099 passed** (94.65%), mypy strict 177 archivos, ruff, check-arch 3/3. Reviewer: apta para merge (corregidos: TOCTOU GUI + fallback viewer + `mkstemp` envuelto). Merge pendiente `git-ops`.

## Siguiente (etapa 13 — Detector EPP de obra, o 15c — identidad distribuida)
- 15c: `DbIdentityProvider` (SQLite/Postgres) sobre el puerto 15b. 13 EPP y 14 inventario requieren entrenamiento. Roadmap y checklist en `docs/WORKFLOW.md` (skill `new-app`).

## Bloqueos / notas
- Usuario verifica manual: ESC/q+X, ventana del menú con cámara real y **aspecto visual del rediseño 10d**.
- Calibrar con cámara real: `posture.calibration_frames` y `posture.tolerances` (o los umbrales absolutos si `calibration_frames: 0`), `anti_intruder.zone` y `alert.repeat_seconds`, `people_counter.line` (`axis`, `position`, `margin` y `track_timeout_frames`), `min_confidence` y `swap_handedness`.
- Calibrar facial 15a con cámara real: `face_auth.match_threshold` y `min_face_sharpness`; descargar `buffalo_s` (`uv run python scripts/download_models.py`).
- Calibrar roles 15b: `session_timeout_seconds` y decidir `require_login: true` donde aplique.
- Verificación del `.exe` con YOLO/torch, YOLO pose e insightface/onnxruntime pendiente (bundle crece, excluido tangencialmente); regenerar `.exe` para probar assets/icono.
- "Cabeza adelante" solo mide desvío horizontal en 2D (limitación conocida).
- `PENDING-TESTS.md`: verificaciones manuales de etapas 0-9b las hace el usuario.
- Tras editar `opencode.json`/agentes/skills/comandos: reiniciar opencode.
