# Estado — Recognizer

- **Fase actual:** fix 15b-ux2 (contraste overlay + cierre submenú facial) completado; siguiente: 13 (EPP) o 15c (DB distribuida)
- **Rama:** `stage/15b-fix2-face-ux`
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
- Etapas 9b-9c: navegador CDP (`open_tab`/`tab_seek`/`tab_press`), fix Chrome 152 y scroll `Victory`/`Closed_Fist` + mute.
- Etapa 10a: launcher multi-app (menú, import perezoso, `ESC`/`q`); merge `c8c8b9f`.
- Etapa 10b: contador YOLO (`yolo26n.pt` nano CPU); dominio + puerto + `UltralyticsDetector` + HUD `Personas: N`; `.spec` sin torch.
- Etapa 10b-fix: salida ESC/q+X a menú (topmost + `WND_PROP_VISIBLE`, tolerante a `cv2.error`); menú tkinter perezoso + `--no-gui`/`TclError`.
- Etapa 10d: rediseño vintage del menú (`MenuTheme`, badges, logo/icono, Silkscreen en `assets/`); `paths.py` (`_MEIPASS`).
- Etapa 10c: tracking YOLO (ByteTrack `persist=True`), `domain/tracking.py`, puerto `ObjectTracker`, `overlay_people.py` y `people_counter.line`; HUD Personas/Entradas/Salidas.
- Etapa 11: anti-intrusos (`domain/intrusion.py`, puerto `AlertSink`, `alert_sound`/`overlay_intrusion`, runner `anti_intruder.py`); zona + alerta edge-triggered.
- Etapa 12: postura YOLO pose (una vía `model.predict` `yolo26n-pose.pt`); `pose.py` + `posture.py`, puerto `pose_estimator`, `ultralytics_pose`, `overlay_posture`, runner `posture.py`.
- Fixes menú (12): rueda sobre cualquier opción (`<MouseWheel>`, `WHEEL_DELTA`) y padding badge/filas; cámara 1280x720.
- Gate 12 verde: pytest **904 passed** (96.76%), mypy 158, ruff, check-arch 3/3, smoke 9.7 FPS. Reviewer: apta (menores aplicados).
- Fix 12b: `measure_posture` parcial + calibración en `PostureMonitor` (mediana); `PostureSnapshot.calibrating` + HUD "Calibrando"; debounce tolerante.
- Gate 12b verde: pytest **946 passed** (96.67%), mypy 158, ruff, check-arch 3/3; postura headless EXIT 0. Reviewer: apta.
- Fix 10c-fix: `CountingLine` con banda muerta `margin` (hysteresis, `zone()`); lado inicial inmediato, `confirm_frames` en cambios y purga `track_timeout_frames`; config `margin` 0.05.
- Gate 10c-fix verde: pytest **973 passed** (96.75%), mypy 158, ruff, check-arch 3/3; `tracking.py` y `overlay_people.py` 100%. Reviewer: apta.
- Fix 10c-fix2: eje `vertical` por defecto en `people_counter.line` (paso lateral = entradas; `invert` intercambia); horizontal con `axis: horizontal`.
- Etapa 15a: enrolamiento + login facial local (`data/faces/`, F-0001 en `index.json`); `FaceRepository` como seam; InsightFace `buffalo_s` CPU, 5 ángulos + distancia 0.25-0.55, debounce.
- Gate 15a verde: pytest **1033 passed** (94.63%), mypy 169, ruff, check-arch 3/3; facial `[disponible]`. Reviewer: apta (path-traversal + chmod 0700).
- Etapa 15b: roles `admin > operator > viewer` (`identity.py` + `PolicyEngine`, `IdentityProvider`, `FileIdentityProvider` con `session.json`); `EnrolledFace.role` + migración legado; menú filtra por rol y revalida; `FaceAuthConfig` + `AuthError`; merge `fcb7c23`.
- Gate 15b verde: pytest **1099 passed** (94.65%), mypy 177, ruff, check-arch 3/3. Reviewer: apta (TOCTOU GUI + fallback viewer + `mkstemp`).
- Fix 15b-face-ux: submenú facial vintage (`face_menu_gui.py` + nombre/rol), selector cámara en header (`CameraEnumerator`, `device` vía `replace(request)`), marco objetivo en `overlay_face` ligado a `min_face_width_ratio` (default 0.18 + MAX); tests `test_face_menu_gui`/`test_camera_discovery`/`test_face_overlay`.
- Gate fix 15b-face-ux verde: lint OK, mypy strict 183, pytest **1119 passed** (94.59%), check-arch 3/3. Reviewer: apta (refresh permisos + `q`).
- Fix 15b-ux2: overlay facial legible (paneles oscuros + texto claro) y cierre del submenú con `Toplevel.wait_window()` (antes `mainloop()` anidado dejaba el proceso colgado sin interfaz).
- Gate fix 15b-ux2 verde: lint OK, mypy strict 183, pytest **1119 passed** (94.67%), check-arch 3/3.
- Fix 15b-ux3: `FileFaceRepository._known_ids` ignora JSON que no son ids `F-0001` (`session.json` del login rompía `list_all` al reabrir la app).
- Gate fix 15b-ux3 verde: lint OK, mypy strict 183, pytest **1121 passed** (94.60%), check-arch 3/3.
- Fix 15b-lat: búfer de captura mínimo (`CAP_PROP_BUFFERSIZE=1`) + `face_auth.det_size` y `process_every_n_frames` (frame skipping reutilizando la última detección) para cámaras lentas (teléfono/enlace móvil).
- Gate fix 15b-lat verde: lint OK, mypy strict 183, pytest **1123 passed** (94.68%), check-arch 3/3. Commits pendientes `git-ops`.

## Siguiente (etapa 13 — EPP, o 15c — identidad distribuida)
- 15c: `DbIdentityProvider` (SQLite/Postgres) sobre el puerto 15b. 13 EPP y 14 inventario requieren entrenamiento. Roadmap en `docs/WORKFLOW.md` (skill `new-app`).

## Bloqueos / notas
- Usuario verifica manual: ESC/q+X, ventana del menú con cámara real y aspecto visual 10d.
- Calibrar con cámara real: `face_auth.min_face_width_ratio` y `match_threshold`; probar selector con 2 cámaras; `posture.*`, `anti_intruder.zone`, `people_counter.line`, `min_confidence`, `swap_handedness`.
- Verificación del `.exe` con YOLO/torch, YOLO pose e insightface/onnxruntime pendiente; regenerar `.exe` para assets/icono.
- "Cabeza adelante" solo mide desvío horizontal en 2D (limitación conocida).
- Tras editar `opencode.json`/agentes/skills/comandos: reiniciar opencode.
