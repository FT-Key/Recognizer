# Estado — Recognizer

- **Fase actual:** etapa 10b-fix (menú GUI + salida ESC/q+X) completada;
  siguiente: 10c (tracking + zona/línea + overlay)
- **Rama:** `stage/10b-fix-menu-gui` (10b mergeada a `dev` en `2b7a574`)
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
- Etapa 9b: navegador CDP (`open_tab`/`tab_seek`/`tab_press`) + fix Chrome 152.
- Etapa 9c: scroll con `Victory`/`Closed_Fist` sostenidos + mute en menú System.
- Etapa 10a: launcher multi-app (menú, import perezoso, `ESC`/`q`); merge `c8c8b9f`.
- Etapa 10b: contador YOLO (`yolo26n.pt` nano CPU); dominio + puerto +
  `UltralyticsDetector` + runner HUD `Personas: N`; `.spec` sin torch.
- Etapa 10b-fix: salida ESC/q+X a menú (`runtime` TOPMOST + `WND_PROP_VISIBLE`,
  tolerante a `cv2.error`); menú tkinter/ttk perezoso (`menu_gui`, `withdraw/`
  `deiconify`) + `--no-gui`/fallback `TclError`; `gui_runner` inyectable.
- Gate 10b-fix verde: pytest **692 passed** (96.17%), mypy strict 134 archivos,
  ruff 158, check-arch 3/3. Reviewer: sin bloqueantes, 4 infos pendientes.

## Siguiente (etapa 10c — tracking + zona/línea + overlay)
- Tracking (`model.track`), zona/línea de conteo y overlay dedicado.
- Roadmap: 11 anti-intrusos, 12 postura, 13 EPP, 14 inventario, 15 facial.
  Checklist de apps en `docs/WORKFLOW.md` y skill `new-app`.

## Bloqueos / notas
- Usuario verifica manual: ESC/q+X y ventana del menú con cámara real.
- Verificación del `.exe` con YOLO/torch pendiente (bundle ~1 GB, excluido).
- Calibrar `min_confidence` (0.5) y `gestures.swap_handedness` con cámara real.
- `PENDING-TESTS.md`: verificaciones manuales de etapas 0-9b las hace el usuario.
- Tras editar `opencode.json`/agentes/skills/comandos: reiniciar opencode.
