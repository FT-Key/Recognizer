# Desktop simplificado — el proyecto en 1 archivo mental

Este doc aplana la arquitectura hexagonal para ver **quién llama a quién, con qué
datos**. No es código para ejecutar (el real está en `src/recognizer/`), es el mapa
mínimo para entenderlo. Referencia extendida: `docs/DESKTOP-EXPLICADO.md`.

## El programa entero (cada línea con su dato de ejemplo)

```python
import cv2  # OpenCV: cámara + color + ventana
import mediapipe as mp  # modelo preentrenado de gestos
from pynput.keyboard import Controller, Key  # inyecta teclas reales en Windows
from collections import Counter  # cuenta rachas (estabilizador casero)

# --- 1. APERTURA (una vez al arrancar) ---
cam = cv2.VideoCapture(0)  # abre webcam 0 -> cam.isOpened() == True (False = ocupada en Zoom/Meet)
cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)  # pide 640px; lee de vuelta cam.get(WIDTH) == 640.0
base = mp.tasks.python.BaseOptions(model_asset_path="models/gesture_recognizer.task")  # .task ~15 MB, 7 gestos; si falta -> GestureClassifierError
opts = mp.tasks.python.vision.GestureRecognizerOptions(base_options=base, running_mode="VIDEO", num_hands=2)  # VIDEO exige timestamp_ms; con num_hands=1 la 2ª mano se ignora
reco = mp.tasks.python.vision.GestureRecognizer.create_from_options(opts)  # 1-3 s en CPU; entra config -> sale reconocedor listo
# real: adapters/mediapipe_gesture_classifier.py: MediaPipeTasksGestureFacade.open()

keys = Controller()  # -> <Controller object>; aún no envió nada al SO
ACCIONES = {"Thumb_Up": Key.media_volume_up, "Open_Palm": Key.media_play_pause}  # gesto -> tecla; real: config.yaml actions.mappings -> bootstrap.py
racha, confirmado = Counter(), None  # Counter() = {} (todo vale 0); confirmado = None (nada ejecutado aún)

while True:
    # --- 2. LEER: sale (bool, array BGR). Mini-ejemplo 2x2 para ver el dato ---
    ok, bgr = cam.read()  # ok=True + bgr =
    # array([[[255,   0,   0],    # píxel (0,0) = AZUL puro en BGR
    #         [  0, 255,   0]],   # píxel (0,1) = VERDE puro
    #        [[  0,   0, 255],    # píxel (1,0) = ROJO puro en BGR
    #         [ 34, 120, 200]]],  # píxel (1,1) = Azul=34, Verde=120, Rojo=200
    #        dtype=uint8, shape=(2, 2, 3))  -- en real es (480, 640, 3); bgr[240,320] = array([34,120,200])
    if not ok: continue  # ok=False, bgr=None -> se salta (30 fallos seguidos = CameraError en el real)

    # --- 3. CONVERTIR BGR->RGB: mismo píxel, canales 0 y 2 intercambiados ---
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)  # entra bgr, sale rgb =
    # array([[[  0,   0, 255],    # (0,0): era [255,0,0] AZUL en BGR -> ahora [0,0,255] ROJO en RGB (¡mismo píxel!)
    #         [  0, 255,   0]],   # (0,1): verde [0,255,0] -> [0,255,0] (igual, va en el medio)
    #        [[255,   0,   0],    # (1,0): era [0,0,255] ROJO en BGR -> ahora [255,0,0] AZUL en RGB
    #         [200, 120,  34]]],  # (1,1): [34,120,200] -> [200,120,34]
    #        dtype=uint8, shape=(2, 2, 3))  -- sin esto el modelo ve colores cruzados y falla
    img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)  # envuelve: entra rgb (480,640,3) -> sale Image(width=640, height=480, format=SRGB)
    res = reco.recognize_for_video(img, timestamp_ms=12300)  # entra Image + ms=12300 -> sale res =
    # res.hand_landmarks = [[Landmark(x=0.50,y=0.75,z=0.01), ..., Landmark(x=0.55,y=0.30,z=0.02)]]  (21 puntos 0..1; [0]=muñeca, [8]=punta índice)
    # res.handedness     = [[Category("Right", score=0.98)]]   (una mano, derecha 98%)
    # res.gestures       = [[Category("Thumb_Up", 0.93), Category("Pointing_Up", 0.04), ...]]  (mejor primero)
    # sin manos: hand_landmarks=[] handedness=[] gestures=[]  |  con poca luz: Category("Thumb_Up", 0.31)
    # real: adapters/mediapipe_gesture_classifier.py: detect() -> _map_result() -> GestureRecognition(hands=(HandLandmarks(Right, 0.98, (Point(0.50,0.75,0.01), ...)),), detections=(DetectedGesture("Thumb_Up", 0.93, Right),))

    gesto = res.gestures[0][0].category_name if res.gestures else "None"  # [[Thumb_Up 0.93]] -> "Thumb_Up" | [] -> "None" | [[Victory 0.88]] -> "Victory" ([0]=1ª mano, [0]=mejor candidato)
    score = res.gestures[0][0].score if res.gestures else 0.0  # 0.93 = firme (pasa >0.5) | 0.31 = se descarta | 0.0 = sin mano

    # --- 4. ESTABILIZAR: la racha evoluciona así con parpadeo real ---
    racha[gesto] += 1  # f1 "Thumb_Up" -> {"Thumb_Up":1} | f2 "Thumb_Up" -> {"Thumb_Up":2} | f3 "None" -> {"Thumb_Up":2,"None":1} | f4-6 "Thumb_Up" -> {"Thumb_Up":5,..} = CONFIRMA
    if racha[gesto] >= 5 and score > 0.5 and gesto != confirmado:  # SÍ: racha=5,score=0.93,confirmado="Open_Palm" -> True | NO: racha=3 (pronto) / score=0.31 (flojo) / confirmado="Thumb_Up" (repetido)
        confirmado = gesto  # "Open_Palm" -> "Thumb_Up" (no repite hasta soltar; el real publica GestureDetected("Thumb_Up",0.93,Right) y espera GestureReleased)
        # real: publica evento GestureDetected(gesture, confidence, handedness) en el bus

        # --- 5. ACTUAR: el gesto confirmado llega al SO ---
        if gesto in ACCIONES:  # "Thumb_Up" in ACCIONES -> True (actúa) | "Victory" in ACCIONES -> False (se ignora; real: NoOpAction)
            keys.press(ACCIONES[gesto]); keys.release(ACCIONES[gesto])  # press(media_volume_up)+release(media_volume_up) -> Windows sube 1 paso | press(play_pause)+release -> pausa Spotify/YouTube
        # real: core/actions/dispatcher.py: handle() -> MediaKeyAction.execute() -> PynputKeySender.press_media()

    # --- 6. MOSTRAR: se enseña el mismo array analizado ---
    cv2.imshow("Recognizer", bgr)  # entra bgr (480,640,3) ya pintado: 21 círculos verdes + texto "Thumb_Up 0.93" + rectángulo zona puntero
    if cv2.waitKey(1) & 0xFF in (27, ord("q")): break  # sin tecla -> -1 (&0xFF=255, sigue) | ESC -> 27 (sale) | q -> 113 (sale)
```

Eso es todo. El proyecto real hace **exactamente esto**, solo que cada paso vive en
su módulo con tipos, tests y config.

## Cadena de llamadas con datos (qué pasa con 1 frame)

| Paso | Quién llama a quién | Datos que viajan | Archivo real |
|------|---------------------|------------------|--------------|
| 1. Leer | `run_camera_loop` → `OpenCVCamera.read()` → `cv2.VideoCapture.read()` | sale `Frame(data=array_bgr, timestamp=12.3)` | `cli/runtime.py`, `adapters/camera_opencv.py` |
| 2. Convertir | `GestureDetectionProcessor` → `MediaPipeGestureClassifier.classify(frame)` | `BGR --cvtColor--> RGB --mp.Image--> MediaPipe` | `adapters/mediapipe_gesture_classifier.py:_to_mp_image` |
| 3. Reconocer | `classify()` → `reco.recognize_for_video(img, ms)` | sale `GestureRecognition(hands=(...21 puntos...), detections=(("Thumb_Up", 0.93, Right),))` | mismo archivo, `_map_result` |
| 4. Estabilizar | `GestureStabilizerProcessor.process(ctx)` cuenta rachas por mano | si `Thumb_Up` 5 frames seguidos y score>0.5 → publica `GestureDetected("Thumb_Up", 0.93, Right)` en el bus | `core/pipeline/gesture_stabilization.py` |
| 5. Despachar | bus → `GestureActionDispatcher.handle(GestureDetected)` → `mapping[Thumb_Up].execute(ctx)` | `ActionContext(gesture, confidence, handedness, timestamp)` | `core/actions/dispatcher.py` |
| 6. Ejecutar | `MediaKeyAction.execute()` → `PynputKeySender.press_media()` → `pynput.press(Key.media_volume_up)` | tecla multimedia al SO (sube volumen) | `core/actions/local.py`, `adapters/pynput_keys.py` |
| 7. Dibujar | overlays (`LandmarkOverlay`, `GestureOverlay`) pintan sobre `frame.data` → `cv2.imshow` | el mismo array BGR con círculos + texto | `adapters/overlay_opencv.py`, `cli/runtime.py` |

## Los otros 3 caminos (mismo esquema)

- **Puntero:** paso 4 bis — si el gesto estable es `Pointing_Up`, `PointerDetectionProcessor` toma el landmark 8 (punta del índice, `x,y` 0..1), lo proyecta fuera de la zona `0.2–0.8` a pantalla y publica `PointerMoved(x, y)` → `PointerMover` → `pynput.mouse.Controller.position = (px, py)`. Pinza pulgar-índice = `PointerClicked` → click izquierdo.
- **Script/comando:** paso 6 alternativo — `ScriptAction.execute()` → `SubprocessScriptRunner.run()` → `subprocess.Popen(["powershell", "-File", "scripts/...ps1"])`. El `path/args` sale de `config.yaml`.
- **Navegador CDP:** paso 6 alternativo — `TabSeekAction.execute()` → `ChromiumCdpBrowser.seek_media()` → HTTP+WebSocket a `localhost:9222` → `Runtime.evaluate("video.currentTime = dur*0.4")` en la pestaña YouTube.

## Dónde vive cada pieza del pseudocódigo

```
cam.read()              → adapters/camera_opencv.py (OpenCVCamera)
cvtColor + mp.Image     → adapters/mediapipe_gesture_classifier.py (_to_mp_image)
recognize_for_video     → mediapipe (librería) tras cargar models/gesture_recognizer.task
racha / confirmado      → core/pipeline/gesture_stabilization.py (N=5/M=5)
ACCIONES[ gesto ]        → config.yaml actions.mappings → bootstrap.py lo convierte en objetos
keys.press              → adapters/pynput_keys.py (teclado) / pynput_mouse.py (mouse) /
                          subprocess_script.py (scripts) / chromium_cdp.py (navegador)
imshow                  → cli/runtime.py + adapters/overlay_opencv.py
```

## Por qué el proyecto real tiene más archivos

Cada "complicación" aísla un cambio futuro o un efecto testeable:

- **Puertos (`core/ports/`)** — para probar sin cámara/teclado (fakes en tests).
- **Eventos + bus** — para que detección, acciones y puntero no se llamen entre sí directamente.
- **Estabilizador** — sin él, cada parpadeo del modelo dispararía la acción 30 veces/seg.
- **Decoradores `Gated(Debounced(Logged))`** — cooldown 1 s + tecla `a` on/off + logs.
- **Pydantic + `config.yaml`** — fallar al arrancar con mensaje claro en vez de a mitad del stream.
