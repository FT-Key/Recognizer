# Estado — Recognizer

- **Fase actual:** etapa 18 (conteo de autos) implementada; gate pendiente de ejecución manual
- **Rama:** `dev`
- **Actualizado:** 2026-09-20

## Hecho
- Repo `FT-Key/Recognizer` (`main`/`dev`); uv + Python 3.12; deps (+`ultralytics`).
- Etapas 0-8: core base, cámara/CLI `smoke`, manos+gestos, acciones locales (media/hotkey/command/script), puntero virtual, gestos personalizados/compuestos y enlaces.
- Etapas 9-9c: web React + `.exe` PyInstaller + `/health`; navegador CDP (`open_tab`/`tab_seek`/`tab_press`) y scroll `Victory`/`Closed_Fist`.
- Etapas 10a-10d: launcher multi-app vintage (`MenuTheme`, tkinter, `ESC`/`q`), contador YOLO (`yolo26n.pt`) + tracking ByteTrack y línea con banda muerta.
- Etapa 11: anti-intrusos (`intrusion.py`, puerto `AlertSink`, zona + alerta edge-triggered).
- Etapas 12-12b: postura YOLO pose (`yolo26n-pose.pt`), calibración por mediana y HUD "Calibrando".
- Etapa 15a: enrolamiento + login facial local (`data/faces/`); `FaceRepository`, InsightFace `buffalo_s` CPU.
- Etapa 15b: roles `admin > operator > viewer` (`identity.py` + `PolicyEngine`, `IdentityProvider` con `session.json`).
- Fixes 15b: submenú vintage + selector cámara + marco objetivo, overlay legible, cierre `wait_window`, `session.json` ignorado, latencia (búfer 1 + frame skipping), captura asíncrona (`LatestFrameSource` + worker), doble apertura y coste (`allowed_modules`, `max_inference_fps`).
- Etapa 15c: gestión de usuarios/accesos; fotos (`<id>.png`), `AccessEvent` + `AccessLogRepository` (`data/access/logins.jsonl`), paneles admin Usuarios y Accesos.
- Fixes 15c: redirección con cuenta regresiva, visor modal, formulario coherente, submenú rediseñado, "Cerrar sesión" rojo con confirmación.
- Release **v0.2.0** en GitHub (launcher + contador/anti-intrusos/postura + facial con roles); `docs/RELEASE-v0.2.0.md`.
- Etapa 15d: clave de respaldo por usuario. `core/domain/credentials.py` (PBKDF2-HMAC-SHA256, 600k iter, sal 16B, `compare_digest`, dummy hash anti-enumeración), `EnrolledFace.password_hash` (legado `""`), `FaceAuthConfig.min_password_length` (4), enrolamiento pide clave+confirmación, login sin cámara (`run_face_login_password` + `face_password_gui.py`), panel de usuarios con columna "Clave".
- Gate 15d verde: lint OK, mypy strict 206, pytest **1250 passed** (95.57%), check-arch 3/3, smoke 17.0 FPS. Reviewer: apta (hallazgos menores aplicados). Merge `0d5ee24` en `dev` (push OK).
- Etapa 15d-accesos-clave: `AccessEvent` con `method` (`facial`/`clave`) y `success` (legado → facial exitoso); el login con clave exitosa y los intentos fallidos quedan registrados; tabla con Método/Resultado en verde/rojo y detalle con banner ("Inicio con clave exitoso/fallido", "Inicio facial exitoso") y nota de falta de foto con clave.
- Etapa 15d-login-dni-ux: login solo por ID (`F-0001`) o DNI (el nombre ya no autentica; homónimos); `EnrolledFace.national_id` (7-8 dígitos, único, legado `""`); Enter envía el diálogo de clave y el fallo muestra error rojo con reintento; enrolamiento y CRUD validan con mensajes visibles. Gate verde (1281 passed, 95.63%). Reviewer: apta.
- Etapa 15d-intento-id: el acceso guarda lo ingresado (`attempted`, nunca la clave) y el motivo (`ID/DNI desconocido` vs `clave incorrecta`); tabla y detalle lo muestran en rojo; IDs nuevos aleatorios `F-A3F9` no secuenciales (legado válido). Gate verde (1284 passed, 95.58%). Reviewer: apta.
- Etapa 16: asistencia (`assistance`). `AssistanceMonitor` (dominio puro, debounce confirm/release), `raised_arms` (muñeca sobre hombro, `raise_margin: 0.05`, `required_arms: 2` configurable a 1). Runner `run_assistance` con una sola vía de inferencia (reutiliza `yolo26n-pose.pt` + `PoseEstimator`), alerta edge-triggered. Overlay con brazos hombro-codo-muñeca, resaltado del lado levantado, HUD y banner. `config.yaml` con `AssistanceConfig`. Gate verde (lint, mypy strict, 80/80 targeted pass, check-arch). Pendiente smoke con cámara real.
- Etapa 18: conteo de autos (`vehicle_counter`). `VehicleCounterConfig`, `AppId.VEHICLE_COUNTER` (`implemented=True`), runner `cli/apps/vehicle_counter.py`, overlay `adapters/overlay_vehicle.py`, import perezoso en `menu.py`, sección `vehicle_counter` en `config.yaml`. Reutiliza `LineCrossingCounter` + `UltralyticsDetector`. Tests en `tests/unit/test_vehicle_counter.py` (17 casos). Gate lint+typecheck verde; pytest pendiente de ejecución manual.

## Siguiente (roadmap `docs/ROADMAP.md`)
- Gate etapa 18: `uv run pytest tests/unit/ -x -q --tb=short` + `uv run check-arch` (ver `docs/history/stage-18-vehicle-counter.md`).
- 19 privacidad (`privacy_blur`): desenfoque de caras/patentes en vivo.
- Luego: 20 caídas / 21 edad-género / 22 somnolencia; final 23 OCR; menor prioridad 13 EPP y 14 inventario.

## Bloqueos / notas
- Verificación manual del usuario: diálogo de clave, `.exe` v0.2.0, ESC/q+X y aspecto visual del menú 10d.
- Calibrar con cámara real: `face_auth.min_face_width_ratio`/`match_threshold`, selector con 2 cámaras, `posture.*`, `anti_intruder.zone`, `people_counter.line`, `min_confidence`, `swap_handedness`.
- "Cabeza adelante" solo mide desvío horizontal en 2D (limitación conocida).
- Tras editar `opencode.json`/agentes/skills/comandos: reiniciar opencode.
