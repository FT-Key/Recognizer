# Estado — Recognizer

- **Fase actual:** etapa 9 (app web React + empaquetado de escritorio con PyInstaller)
  implementada en el árbol de trabajo (sin commit/merge); siguiente: etapa 10
  (enrolamiento facial, roles y despliegue web)
- **Rama:** `dev` (trabajo de etapa 9 sin commitear; ver `git status`)
- **Actualizado:** 2026-09-15

## Hecho
- Repo git: `main` inicial, `dev`, `stage/0-setup`; remoto `FT-Key/Recognizer` configurado.
- uv + Python 3.12.14; dependencias runtime y dev instaladas (mediapipe 1.0.1, opencv 5,
  pydantic 2.13, pynput, pytest, ruff, mypy, import-linter).
- Core base: `Frame`, puerto `FrameSource`, `AppConfig`/`CameraConfig`, errores del dominio.
- Adaptador `OpenCVCamera` (inyectable, testeable), CLI `smoke` y modelos en `models/`.
- Etapa 0 con gate verde: pytest 21 tests, 98% cobertura y smoke real a 29.3 FPS.
- Etapa 1 (manos): puerto `HandTracker` + `MediaPipeHandTracker`, `EventBus` tipado +
  `HandsDetected`, `PipelineBuilder` + `HandDetectionProcessor` y overlay OpenCV.
- Etapa 2 (gestos): `GestureRecognizer` de MediaPipe, puerto `GestureClassifier`,
  `GestureDetectionProcessor` + `GestureStabilizerProcessor` (N=5/M=5), eventos
  `GestureDetected`/`GestureReleased` y `GestureOverlay`.
- Etapa 3 (acciones locales): `Action`/`MediaKey`/`ActionContext`, puertos `KeySender` y
  `CommandRunner`, acciones media key/hotkey/command/no-op con
  `Gated(Debounced(Logged(...)))`, dispatcher con fallback no-op, `ActionsConfig` en
  `config.yaml`, adaptadores pynput/subprocess y entrypoint `recognizer` con HUD (tecla `a`).
- Etapa 4 (puntero virtual): `PointerPosition`/`PointerCalibration` y evento
  `PointerMoved`; `PointerDetectionProcessor` (landmark 8 con gesto estable) y
  `PointerMover` con gate compartido; Strategy de suavizado `none`/`ema` (alpha 0.35);
  puerto `MouseController` + `PynputMouseController`; `PointerConfig`/`ActiveZoneConfig`
  en `config.yaml` (zona 0.2-0.8, `mirror_x`), `PointerOverlay` y flag `--no-pointer`.
- Gate de etapa 4 en verde: lint (109 archivos), mypy strict (83), pytest (290 tests,
  98.61%), check-arch 3/3 y smoke real OK (30 fotogramas, 4.6 FPS con CPU cargada).
- Etapa 5 (gestos personalizados): vocabulario abierto (`GestureId` + `GestureCatalog`)
  en vez del enum cerrado; reglas geométricas de landmarks en `config.yaml`
  (`gestures.rules`, `rules_priority`, `rule_thresholds`) con `LandmarkRuleProcessor`;
  `gestures.custom_labels` para modelos MediaPipe custom; `config.yaml` con ejemplos
  comentados. Gate verde: pytest 342 tests, 98.72%, mypy 87, check-arch 3/3, smoke 13.7 FPS.
- Etapa 6 (acciones script): puerto `ScriptRunner` + `SubprocessScriptRunner` (intérprete
  por formato `.py/.ps1/.bat/.cmd/.sh`, bloqueante/no bloqueante, `timeout_seconds`
  obligatorio si bloqueante, contexto `RECOGNIZER_*` opt-in) y acción `script` en
  `config.yaml`. Gate verde: pytest 378 tests, 98.81%, mypy 92, check-arch 3/3, smoke 11.5 FPS.
- Etapa 7 (abrir enlaces): puerto `LinkOpener` + `ChromeLinkOpener` (autodetección de
  Chrome; `chrome.exe <url>` abre pestaña o lanza el navegador) y acción `open_links` con
  playlist secuencial rotatoria; `ILoveYou` mapeado a un enlace de YouTube. Ejemplo de
  script de usuario en `scripts/actions/log_gesture.py`. Gate verde: pytest 399 tests,
  98.86%, mypy 97, check-arch 3/3, smoke 17.1 FPS.
- Etapa 8 (gestos compuestos): menús por mano (`actions.menus`) con `HandGestureTracker` y
  resolución en el dispatcher (consume trigger, anti-repetición), puntero desactivado con
  2 manos, `gestures.swap_handedness`, `MenuOverlay` y script `scripts/actions/video_start.ps1`
  (vuelve el video de Chrome al inicio). Gate verde: pytest 442 tests, 98.94%, mypy 99,
  check-arch 3/3, smoke 13.3 FPS.
- Merges `--no-ff` a `dev` y push: etapa 0 (b613aeb), etapa 1 (c57e425), etapa 2
  (c23da42), etapa 3 (15e5fb9), etapa 4 (4da3e35), etapa 5 (a266db7), etapa 6 (1e5f36e)
  y etapa 7 (656478a).
- Documentación: arquitectura, workflow, web-plan, historial; opencode con 5 subagentes,
  2 skills y 4 comandos.
- Etapa 9 (web React + empaquetado): app web en `web/` migrada a React 19 + Vite con
  MediaPipe en **Web Worker** (fallback GPU→CPU), lógica pura en `src/lib`, hooks y
  componentes; tema claro/oscuro persistente; **banner dinámico** que detecta la app de
  escritorio vía `http://127.0.0.1:8765/health`; gestos personalizados con
  `scripts/train_gesture_model.py` (Model Maker). Escritorio empaquetado con PyInstaller
  (`packaging/recognizer.spec` onedir + `scripts/build_exe.py` → `dist/Recognizer/`),
  servidor de salud local (`adapters/health_server.py`) y resolución de rutas junto al
  `.exe`. Gate verde: pytest 492 tests, 98.38%, mypy 107 archivos, check-arch 3/3;
  `npm run build` OK; `.exe` verificado (`--help`, frames headless y `GET /health`).
  El `.exe` escribe `logs/recognizer.log` junto al ejecutable (config, pantalla, modelo y
  crashes). Bug del puntero en el `.exe` corregido: faltaba `tkinter` en el bundle (lo usa
  `pynput_mouse` para el tamaño de pantalla) y los fallos inesperados de acción/puntero ya
  no tumban la app. Web desplegada en Vercel y corregida: shim de `importScripts` para
  MediaPipe en Web Worker, estabilizador con transición entre gestos, overlay espejado y
  textos con escapes `\uXXXX`. Ver `docs/history/stage-9-web-react-y-empaquetado.md`,
  `docs/WEB-PLAN.md` y `docs/DESKTOP-APP-PLAN.md`.

## Siguiente (etapa 10 — enrolamiento y despliegue)
- Enrolamiento facial, roles/permisos por gesto y despliegue web (Vercel/GitHub Pages).

## Bloqueos / notas
- Verificaciones manuales de etapas 0-8 (gestos, acciones reales, puntero, reglas de
  landmarks, scripts, enlaces, menús compuestos y FPS) consolidadas en
  `docs/PENDING-TESTS.md`; las ejecuta el usuario cuando pueda.
- Calibrar `gestures.swap_handedness` con la cámara real (izquierda/derecha).
- Pendiente decidir la nueva funcionalidad de los gestos `Pointing_Up` y `Victory`.
- Tras editar `opencode.json`, agentes, skills o comandos: reiniciar opencode.
- `uv` no está en el PATH de sesiones ya abiertas; una terminal nueva lo tendrá.
