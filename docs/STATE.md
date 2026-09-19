# Estado — Recognizer

- **Fase actual:** etapa 11 (anti-intrusos: zona + alerta) completada; siguiente: 12 (postura con YOLO pose)
- **Rama:** `stage/11-anti-intruder` (10c mergeada a `dev` en `1e8a5a6`)
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
- Etapa 10b: contador YOLO (`yolo26n.pt` nano CPU); dominio + puerto +
  `UltralyticsDetector` + runner HUD `Personas: N`; `.spec` sin torch.
- Etapa 10b-fix: salida ESC/q+X a menú (topmost + `WND_PROP_VISIBLE`, tolerante a
  `cv2.error`); menú tkinter/ttk perezoso (`menu_gui`) + `--no-gui`/fallback `TclError`.
- Etapa 10d: rediseño UX/UI vintage del menú (`MenuTheme`, botones, badges, logo e
  icono, fuente pixel Silkscreen en `assets/`); `paths.py` resuelve assets (`_MEIPASS`).
- Etapa 10c: tracking YOLO (`model.track`, ByteTrack `persist=True`), dominio
  `core/domain/tracking.py` (`CountingLine`/`LineCrossingCounter`), puerto
  `ObjectTracker`, overlay dedicado (`overlay_people.py`) y `people_counter.line`;
  runner con HUD Personas/Entradas/Salidas.
- Etapa 11: anti-intrusos; dominio `core/domain/intrusion.py`
  (`IntrusionZone`/`ZoneIntrusionMonitor`), puerto `AlertSink`, adaptadores
  `alert_sound`/`overlay_intrusion` y runner `cli/apps/anti_intruder.py`; zona +
  alerta sonora edge-triggered; `DetectorConfig` reutilizable por contador/anti-intrusos.
- Gate 11 verde: pytest **812 passed** (96.57%), mypy strict 148 archivos,
  ruff 173, check-arch 3/3. Reviewer: sin bloqueantes (menores aplicados).

## Siguiente (etapa 12 — postura ergonómica con YOLO pose)
- Postura sobre YOLO pose; reutiliza tracking/overlay. Roadmap: 13 EPP, 14 inventario, 15 facial (checklist en `docs/WORKFLOW.md`, skill `new-app`).

## Bloqueos / notas
- Usuario verifica manual: ESC/q+X, ventana del menú con cámara real y **aspecto
  visual del rediseño 10d** (tamaño, colores, icono en la barra de tareas, teclado).
- Verificación del `.exe` con YOLO/torch pendiente (bundle ~1 GB, excluido); el
  icono y los assets ya van bundleados por el spec (regenerar `.exe` para probar).
- Calibrar con cámara real: `anti_intruder.zone` (x/y, `confirm_frames`/`release_frames`),
  `alert.repeat_seconds`, `people_counter.line`, `min_confidence` y `swap_handedness`.
- Smoke `uv run smoke --frames 30 --no-window` pendiente (cámara real); HUD del
  contador cuenta solo tracks con ID (puede mostrar 0 en el warm-up del tracker).
- `PENDING-TESTS.md`: verificaciones manuales de etapas 0-9b las hace el usuario.
- Tras editar `opencode.json`/agentes/skills/comandos: reiniciar opencode.
