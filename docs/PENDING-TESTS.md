# Tests pendientes (etapas 0-10d) — verificación manual del usuario

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
  Esperado de referencia (ajustes post-etapa 8): 445 passed, 2 deselected, cobertura 98.94%
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

### Click con pulgar abierto (post-etapa 8)

- [ ] `uv run recognizer --verbose`: hacer `Pointing_Up` y abrir el pulgar (V con el
  índice); el overlay debe mostrar la cruz verde + "Click" y en la consola deben aparecer
  líneas `[CLICK] ratio=... umbral=... presionado=True`. Cerrar el pulgar → suelta.
- [ ] Calibración de `pointer.thumb_open_threshold` en `config.yaml`: si el click no
  dispara, bajar el umbral (ej: 0.4); si dispara sin querer, subirlo (ej: 0.6). Anotar
  el valor final.
- [ ] Verificar que el índice no se mueve al abrir/cerrar el pulgar: el cursor debe
  quedarse en el mismo lugar mientras se mantiene `Pointing_Up`.
- [ ] Click sostenido: abrir el pulgar, mover la mano (manteniendo el gesto) y verificar
  que el click sigue presionado (útil para drag).

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

### Etapa 8 — gestos compuestos y script de video

- [ ] Calibrar lateralidad: con una mano izquierda y derecha, comprobar en el overlay que
  `Left`/`Right` coinciden con tu mano real; si están invertidas, poner
  `gestures.swap_handedness: true`.
- [ ] Una sola mano: todo igual que antes (p. ej. `Pointing_Up` mueve el cursor; `Victory`
  mutea). Verificar que con 2 manos el cursor NO se mueve.
- [ ] Gesto compuesto: con la izquierda sosteniendo `Pointing_Up`, hacer `Victory` con la
  derecha y comprobar que NO se mutea (se consume) y que el video de Chrome vuelve al
  inicio. Probar también soltando y repitiendo (no debe repetir sin liberar la derecha).
- [ ] Script de video: con un video reproduciéndose en Chrome, ejecutar el menú y verificar
  que vuelve a 0:00 **y sigue reproduciéndose** (no queda en pausa). Con dos ventanas de
  Chrome, comprobar que actúa sobre la del video reproduciéndose o la más reciente.
  Revisar `scripts/actions/video_start.log`.
- [ ] Añadir una segunda opción a `menus.Replay.options` (p. ej. `Thumb_Up`) y verificar que
  se puede añadir otra con solo config.
- [ ] Overlay: al sostener el modificador izquierdo, ver el nombre del menú y sus opciones.

### Etapa 9b — navegador controlado (CDP)

- [ ] Auto-detección: ejecutar `uv run recognizer --verbose` sin Chrome abierto y verificar
  en el log que detecta el navegador Chromium instalado (Chrome, Edge, Brave, etc.) y lo
  lanza en `--remote-debugging-port=9222`. Con el navegador ya corriendo, verificar que lo
  reutiliza sin lanzar otro proceso.
- [ ] `ILoveYou` abre pestaña: con el navegador corriendo, hacer el gesto `ILoveYou` y
  comprobar que se abre (o enfoca) una pestaña de YouTube con el video configurado. Si la
  pestaña ya existe, debe enfocarla y reproducir; si no, crearla.
- [ ] Menú Replay (izquierda `Pointing_Up`) con las 3 opciones CDP:
  - `Pointing_Up` → `tab_seek` fracción 0.0 → video al inicio.
  - `Victory` → `tab_seek` fracción 0.4 → video al 40%.
  - `OK_Sign` → `tab_seek` fracción 0.7 → video al 70%.
  Verificar que el salto funciona y el video sigue reproduciéndose tras cada seek.
- [ ] `tab_press`: configurar una acción `tab_press` con teclas `["space"]` y comprobar que
  pausa/reproduce el video de la pestaña activa via CDP.
- [ ] Error controlado: sin navegador Chromium instalado, ejecutar y comprobar que la app
  registra un `WARNING` y sigue corriendo sin caerse.
- [ ] Perfil aislado: verificar que se crea `browser-profile/<familia>/` junto a config.yaml
  y que el login de YouTube es opcional (el video funciona sin cuenta).

### Ajustes post-etapa 8 — arranque rápido y menú Replay

- [ ] Arranque rápido: `uv run smoke --frames 30 --no-window` debe abrir la cámara en
  menos de 1 s (antes 20-30 s por las hardware transforms de MSMF). El log de arranque
  muestra el banner `R E C O G N I Z E R` y las etapas `Cargando configuracion`,
  `Abriendo camara (device=N)` y `Cargando modelo de gestos` con su duración en ms.
- [ ] Si la cámara abre pero no entrega fotogramas (`0xC00D3704`), comprobar que no haya
  otra instancia de Recognizer, Chrome o la Cámara de Windows reteniendo el dispositivo.
- [ ] Menú Replay (izquierda sosteniendo `Pointing_Up`) con las 3 opciones de la derecha:
  - `Pointing_Up` → tecla `0` → video al inicio (0%).
  - `Victory` → tecla `4` → video al 40%.
  - `OK_Sign` → tecla `7` → video al 70%.
  Comprobar que `Victory` ya NO mutea en este contexto (se consume) y que tras el salto el
  video sigue reproduciéndose; revisar `scripts/actions/video_start.log` (muestra la tecla
  enviada). Con el modificador sostenido, los gestos de la otra mano que no sean opción no
  ejecutan su acción global (comportamiento de acorde).
- [ ] Calibrar el gesto `OK_Sign`: es una regla de pinza (índice y pulgar se tocan) con
  medio/anular/meñique extendidos; la distancia se normaliza por el tamaño de la mano
  (`distance.max_ratio: 0.35`). Verificar en el overlay que se detecta al hacer la señal OK;
  si no dispara, subir `max_ratio` (o bajarlo si hay falsos positivos).

### Etapa 10a — launcher multi-app (menú)

- [ ] `uv run recognizer` sin argumentos abre el menú con las 7 apps en orden: 1 gestos
  `[disponible]`, 2-4 `[proximamente]` (sin entrenamiento) y 5-7
  `[proximamente] - requiere entrenamiento/enrolamiento`.
- [ ] `uv run recognizer --list-apps` lista el menú y sale sin abrir la cámara.
- [ ] Seleccionar `1`: abre la app de gestos; `ESC`/`q` vuelve al menú principal (no cierra
  el programa) y se registra `Volviendo al menu principal.`.
- [ ] Seleccionar `2`, `3` o `4`: avisa `aun no esta implementada (proximamente)` y sigue en
  el menú, sin abrir cámara.
- [ ] Seleccionar `5`, `6` o `7`: avisa que requiere entrenamiento/enrolamiento y sigue en
  el menú.
- [ ] Opción inválida (`abc`, `99`, vacío) y `0`/`q`/`salir`/`exit`: mensaje y salida limpia.
- [ ] `apps.enabled.gestures: false` en `config.yaml`: la opción 1 pasa a
  `[deshabilitada]` y no se puede lanzar; restaurar a `true` al terminar.
- [ ] Rendimiento: abrir el menú no debe cargar MediaPipe ni abrir la cámara; el arranque es
  inmediato (sin espera de inferencia). Anotar si el primer `1` tarda lo esperado.
- [ ] `.exe`: doble clic abre el menú en consola; `ESC`/`q` dentro de gestos vuelve al menú.

### Etapa 10b — contador de personas (YOLO)

- [ ] `uv run recognizer`, elegir `2` (Contador de personas): debe abrir la cámara, cargar
  `yolo26n.pt` (se autodescarga a `models/` si falta) y dibujar cajas + HUD `Personas: N`.
- [ ] `ESC`/`q` (o la X) vuelve al menú; anotar FPS con 0/1/2 personas en cuadro.
- [ ] Calibrar `people_counter.min_confidence` en `config.yaml` (0.5 por defecto): bajarlo si
  no detecta, subirlo si hay falsos positivos.
- [ ] `.exe`: pendiente de regenerar con `assets`/icono; verificar que el contador arranca
  (torch/YOLO siguen excluidos del bundle, bundle ~1 GB).

### Etapa 10c — contador con tracking y línea

- [ ] `uv run recognizer`, elegir `2`: se dibujan cajas con `#id`, la línea amarilla
  horizontal (por defecto `position: 0.5`) y el HUD `Personas` / `Entradas` / `Salidas`.
- [ ] Cruzar la línea de arriba abajo: aumenta `Entradas`; de abajo arriba: `Salidas`.
  Con `people_counter.line.invert: true` se intercambian. Probar `axis: vertical`.
- [ ] Anti-jitter: quedarse justo sobre la línea no debe sumar; `confirm_frames: 2`
  exige 2 fotogramas consecutivos al otro lado. Ajustar si hay doble conteo o cruces
  perdidos.
- [ ] `ESC`/`q`/`X` vuelve al menú; el resumen final reporta personas, entradas y
  salidas. Anotar FPS con 0/1/2 personas.
- [ ] Nota: durante el warm-up del tracker el HUD puede mostrar `Personas: 0` hasta
  que YOLO asigna IDs.

### Etapa 10b-fix — salida a menú y menú GUI

- [ ] Dentro de cualquier app (`1` gestos, `2` contador), `ESC`/`q` vuelve al menú **con la
  ventana de la cámara enfocada**; la `X` de la ventana también vuelve al menú.
- [ ] `uv run recognizer` sin argumentos abre la ventana del menú (tkinter); al elegir una app
  y salir, la ventana del menú reaparece.
- [ ] `uv run recognizer --no-gui` usa el menú de consola; sin display también cae a consola.

### Etapa 10d — rediseño visual del menú (Vintage)

- [ ] Aspecto general: ventana amplia y centrada, colores teal/plata, biseles retro, textos
  legibles; **todas las apps visibles** (si la pantalla es baja, scroll vertical).
- [ ] Cada app es un **botón**; las no implementadas se ven deshabilitadas con su badge
  (`PRÓXIMAMENTE`/`DESHABILITADA`) y no se pueden abrir.
- [ ] **Icono del logo** (mismo `minilogo` de la web) visible en la barra de título y en la
  barra de tareas de Windows.
- [ ] Tipografía pixel (Silkscreen) en título/secciones/badges; si no se registra, cae a una
  monoespaciada (anotar qué se ve).
- [ ] Teclado: flechas ↑/↓ mueven el foco entre apps, `Enter`/espacio abren la enfocada, `ESC`
  cierra, `Tab` navega; el foco se ve resaltado.
- [ ] Contraste: los textos sobre badges y cabecera se leen bien (sin gris sobre gris).
- [ ] Regenerar assets si cambia el logo de la web: `uv run python scripts/build_assets.py`.

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
