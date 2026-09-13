# Tests pendientes (etapas 0-7) — verificación manual del usuario

El cierre de la etapa 4 se hizo con el gate automático verde (lint, mypy strict, 290 tests
con 98.61% de cobertura, check-arch 3/3 y smoke real), pero las verificaciones
manuales/físicas de las etapas 0-4 las ejecuta el usuario cuando pueda. Este documento es
la lista de cierre: marcar cada ítem y anotar la evidencia real (fecha, equipo, FPS, gestos
y efectos observados).

## Preparación

- Abrir una terminal nueva para tener `uv` en el PATH (las sesiones ya abiertas no lo
  tienen). Fallback: usar los ejecutables de `.venv\Scripts` con los mismos comandos,
  p. ej. `.venv\Scripts\pytest.exe` o `.venv\Scripts\python.exe -m pytest`.
- Modelos ya descargados en `models/`: `hand_landmarker.task`, `gesture_recognizer.task`
  y `blaze_face_short_range.tflite`.
- Cámara a 640x480 (`config.yaml`), buena iluminación y mano a 40-60 cm de la cámara.
- Cerrar Chrome, VS Code, TeamViewer y opencode para medir FPS limpio; anotar el equipo y
  la carga de CPU observada junto a cada medición.
- Ejecutar todo desde la raíz del repo: `config.yaml` y `models/` se resuelven por ruta
  relativa.

## Gate automático

Ejecutar en este orden y anotar el resultado real de cada comando:

- `uv run lint` — ruff check + format. Esperado: sin errores.
- `uv run typecheck` — mypy --strict. Esperado: "Success: no issues found".
- `uv run test` — pytest unitario con cobertura (excluye los marcados `integration`).
  Esperado de referencia (etapa 7): 399 passed, 2 deselected, cobertura 98.86%
  (umbral 80%).
- `uv run check-arch` — import-linter. Esperado: 3/3 contratos KEPT.
- `uv run pytest -m integration` — 2 tests reales de MediaPipe sin cámara:
  `tests/integration/test_mediapipe_hand_tracker_integration.py` y
  `tests/integration/test_mediapipe_gesture_classifier_integration.py`. Esperado:
  "2 passed, 290 deselected". Nota: como `addopts` incluye `--cov-fail-under=80` y la
  suite unitaria queda deseleccionada, el comando termina con cobertura ~65% y sale con
  código distinto de cero; usar `uv run pytest -m integration --no-cov` para una
  ejecución limpia (el gate de cobertura real es `uv run test`).
- `uv run smoke --frames 30 --no-window` — cámara + modelo de gestos. Esperado: sin
  excepciones y un resumen final `Smoke OK: 30 fotogramas, ...` con FPS medio, máximo de
  manos y gestos confirmados.

## Checklist por etapa

### Etapa 0 — referencia (informativa)

- [ ] `uv run smoke --frames 30 --no-window` sin inferencia: fue el baseline del proyecto
  con 29.3 FPS reales. Solo se usa como referencia de comparación; no hay nada que
  verificar aquí salvo que el comando siga funcionando.

### Etapa 1 — manos

- [ ] `uv run smoke --frames 120 --no-window` mostrando las 2 manos: el log cada 30
  fotogramas y el resumen final deben indicar `Manos max: 2` / `maximo de manos: 2`.
  Criterio físico pendiente: FPS >= 20 con 2 manos a 640x480 en equipo descargado.
  Anotar FPS medio y carga de CPU. Baseline real: 29.3 FPS sin inferencia (etapa 0); el
  día de la medición de la etapa 1 (CPU muy cargada) el pipeline de manos dio 9.3 FPS y
  `--no-hands` 25.1 FPS; la detección aislada costó 62-72 ms/fotograma (13.8-16.2 FPS).
- [ ] `uv run smoke --frames 120 --no-window --no-hands` en las mismas condiciones:
  aísla el coste de la inferencia y permite repetir la comparación de FPS. Anotar el
  resultado junto al anterior.

### Etapa 2 — gestos

- [ ] `uv run smoke --frames 180` (con ventana): mostrar `Victory`, retirar la mano y
  mostrar `Open_Palm`. El resumen final debe reportar al menos 1 `GestureDetected` de
  cada uno: `gestos confirmados: Victory=..., Open_Palm=...` (puede haber más).
- [ ] Anti-parpadeo (`stabilization_frames: 5`, `release_frames: 5`): un gesto no se
  confirma hasta 5 fotogramas consecutivos y se libera tras 5 ausencias. Procedimiento:
  mostrar `Victory` medio segundo y cambiarlo de inmediato (no debe confirmarse antes de
  los 5 fotogramas); después retirar la mano y comprobar en el resumen que aumenta el
  contador de `GestureReleased`.
- [ ] No-regresión de FPS frente a la etapa 1 en igualdad de carga: comparar la medición
  con los FPS anotados en la etapa 1 bajo carga similar. Referencia real: etapa 2 midió
  8.2 FPS con CPU al 39-87% por carga externa y sin manos en cámara; etapa 1 en
  condiciones similares: 9.3 FPS.

### Etapa 3 — acciones

- [ ] `uv run recognizer` (con ventana) y probar cada mapeo por defecto de `config.yaml`:
  `Thumb_Up` sube el volumen, `Thumb_Down` lo baja, `Closed_Fist` mutea, `Open_Palm`
  reproduce/pausa y `Victory` lanza `ctrl+shift+m`. Para ver el efecto del atajo, abrir
  una pestaña de Chrome/navegador (p. ej. un video) y comprobar que `Victory` la mutea.
- [ ] Tecla `a`: alterna el HUD entre `Acciones: ON` (verde) y `Acciones: OFF` (rojo) y
  los logs muestran `Acciones activadas`/`Acciones desactivadas`. Con el HUD en OFF,
  repetir `Thumb_Up` y comprobar que no cambia el volumen ni se registra ejecución.
- [ ] Debounce (`cooldown_seconds: 1.0`): mantener el gesto o re-confirmarlo dentro del
  segundo no repite la acción (una sola línea `Ejecutando ...` por ventana de 1 s).
  Esperar más de un segundo, soltar y repetir el gesto: la acción se ejecuta de nuevo.
- [ ] `uv run recognizer --no-actions`: no ejecuta ninguna acción y el HUD pasa a
  `Puntero: ON/OFF` (el puntero sigue activo con la tecla `a`), aunque los gestos se sigan
  detectando. Para no tener HUD ni efectos usar `--no-actions --no-pointer`.
- [ ] Comando real: descomentar en `config.yaml` el ejemplo
  `ILoveYou -> command [notepad.exe]`, ejecutar `uv run recognizer`, hacer `ILoveYou` y
  verificar que se abre el Bloc de notas. Volver a comentarlo al terminar.
- [ ] Errores controlados: configurar `argv: [no-existe.exe]` (comando inválido) o
  `keys: [ctrl, kk]` (tecla desconocida), ejecutar y comprobar que la app registra un
  `WARNING` del tipo `Fallo la accion para ...` y sigue corriendo; no se cae.
- [ ] Cierre limpio: `ESC` o `q` cierran el bucle sin excepciones, se registra el resumen
  final `App OK: ...` y la ventana se destruye.

### Etapa 4 — puntero virtual

- [ ] `uv run recognizer` (con ventana) y mostrar `Pointing_Up`: el cursor sigue la punta
  del índice con suavizado y se detiene al retirar el gesto; el resumen final debe
  reportar `PointerMoved` > 0 y `Puntero: activado`.
- [ ] Sentido: con `mirror_x: true` (default), mover la mano a la derecha en vista espejo
  mueve el cursor a la derecha; probar `mirror_x: false` y confirmar la inversión.
- [ ] Calibración: alcanzar las 4 esquinas de la pantalla desde la zona cómoda; si no se
  llega o resulta hipersensible, ajustar `pointer.active_zone` en `config.yaml`.
- [ ] Suavizado: comparar `smoothing: none` con `ema` y alpha 0.2/0.5/0.8; anotar el
  elegido.
- [ ] Gate: con la tecla `a` en OFF el puntero se detiene; con ON vuelve (el HUD muestra
  `Acciones: OFF` o `Puntero: OFF` según lo que esté activo).
- [ ] `uv run recognizer --no-pointer`: el puntero no se mueve, pero las acciones y los
  gestos siguen.
- [ ] `uv run recognizer --no-actions` (con puntero on): sin acciones, HUD
  `Puntero: ON/OFF` y puntero activo; `uv run recognizer --no-actions --no-pointer`: sin
  HUD ni efectos.
- [ ] Dos manos en cámara: el cursor sigue solo la mano que apunta.
- [ ] Cierre limpio con `ESC`/`q` y resumen final con el contador `PointerMoved`.
- [ ] FPS: `uv run smoke --frames 120 --no-window` (no mueve el ratón) comparado con las
  etapas previas bajo carga similar; anotar FPS medio y carga de CPU.

### Etapa 5 — gestos personalizados (reglas de landmarks)

- [ ] Reglas en config: descomentar `rules:` en `config.yaml` con `L_Sign` y
  `One_Finger_Up`, y mapear `L_Sign` (por ejemplo) a una acción. Ejecutar
  `uv run recognizer` y comprobar que el overlay muestra el nombre del gesto de regla.
- [ ] `rules_priority`: con `rules_first`, `One_Finger_Up` compite con `Pointing_Up` del
  puntero. Verificar que con `model_first` el puntero sigue funcionando y con `rules_first`
  la regla tiene preferencia. Anotar el elegido.
- [ ] `custom_labels` (requiere modelo custom): entrenar/obtener un `.task` de Model Maker,
  apuntar `gestures.model_path`, declarar sus etiquetas en `custom_labels` y mapear una a
  una acción. Verificar que se detecta y ejecuta. Pendiente de tener el modelo custom.
- [ ] Ajustar `rule_thresholds` (`straight_angle_deg`, `direction_tolerance_deg`) según tu
  mano y anotar los valores que mejor funcionan.

### Etapa 6 — acciones script

- [ ] No bloqueante: mapear un gesto a `type: script` con `blocking: false` apuntando a un
  `.py` que escriba un archivo. Verificar que el archivo se crea y que la cámara sigue.
- [ ] Bloqueante: `blocking: true` con `timeout_seconds` (p. ej. 5). Verificar que espera,
  que la cámara se detiene mientras corre, y que al superar el timeout registra un
  `WARNING` y la app continúa.
- [ ] Los 4 formatos: probar `.py`, `.ps1`, `.bat`/`.cmd` y `.sh` (este último requiere
  `bash` instalado; si no, debe fallar con `ActionError` controlado y seguir la app).
- [ ] `interpreter`: verificar `auto` por extensión y forzar uno distinto (p. ej. `.txt`
  con `interpreter: python`).
- [ ] Contexto: con `pass_context: true`, un script que imprima/registre las variables
  `RECOGNIZER_GESTURE/_HANDEDNESS/_CONFIDENCE/_TIMESTAMP`; comprobar los valores.
- [ ] Errores: `path` inexistente y comando inválido → `WARNING` tipo
  `Fallo la accion para ...` y la app sigue corriendo.

### Etapa 7 — abrir enlaces

- [ ] Cerrar Chrome y hacer `ILoveYou`: debe lanzarse Chrome y entrar al enlace de
  YouTube. Anotar si abre y si el vídeo empieza (el autoplay puede requerir interacción).
- [ ] Con Chrome ya abierto, repetir `ILoveYou`: debe abrirse en una pestaña nueva de la
  ventana existente, no en un proceso nuevo.
- [ ] Playlist secuencial: añadir un segundo enlace en `actions.mappings.ILoveYou.urls` y
  comprobar que el primer `ILoveYou` abre el 1.º, el siguiente el 2.º y luego vuelve al 1.º
  (sin aleatoriedad).
- [ ] `browser` vacío (autodetección) y con ruta explícita a `chrome.exe`; probar en un
  equipo donde Chrome esté en una ruta no estándar.
- [ ] Chrome ausente: sin Chrome instalado debe registrarse un `WARNING` tipo
  `Fallo la accion para ILoveYou: No se encontro Chrome...` y la app seguir corriendo.
- [ ] Script de ejemplo: mapear un gesto a `type: script` con
  `path: scripts/actions/log_gesture.py` y `pass_context: true`; comprobar que se crea
  `scripts/actions/gesture_log.txt` con el gesto.

## Notas de registro

- Marcar cada checkbox al completarlo y anotar fecha, equipo, carga de CPU y FPS en cada
  medición; adjuntar el fragmento de log relevante.
- Si algo falla, describir el fallo con el comando exacto y el log, actualizar
  `docs/STATE.md` (fase 5) y abrir una incidencia en GitHub si no se corrige en el acto.
- Las mediciones de FPS solo son comparables si el equipo y la carga de CPU son
  similares; repetir la medición descartando el primer resultado si la cámara acaba de
  arrancar.

## Cómo registrar el resultado

Completar la checklist marcando cada ítem y anotar la evidencia real (FPS, gestos
detectados y acciones observadas). Si algo falla, describir el fallo con el comando
  exacto y el log, y actualizar `docs/STATE.md` y el historial de la etapa en curso.
