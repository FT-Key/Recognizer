<p align="center">
  <img src="https://raw.githubusercontent.com/FT-Key/Recognizer/main/web/public/logo.png" alt="Recognizer" width="150" />
</p>

<h1 align="center">Recognizer v0.2.0</h1>

<p align="center">
  Un <b>launcher de visión por computadora</b>: gestos de mano, contador de personas,
  anti-intrusos, postura ergonómica y <b>reconocimiento facial con login</b>.
</p>

---

Recognizer usa tu cámara para reconocer gestos, personas y rostros, y convertir esa
información en acciones reales sobre Windows. Todo el procesamiento corre **100% local**:
tu video nunca sale de tu equipo y no hace falta conexión a internet.

En esta versión `recognizer` abre un **menú de aplicaciones** y elegís cuál usar. Cada app
termina con `ESC` o `q` y vuelve al menú.

## Descarga

**`Recognizer-v0.2.0-win64.zip`** · ~550 MB comprimido · ~1,4 GB descomprimido (aprox.)

<!-- Ajustar los tamaños exactos tras compilar el .exe (con YOLO/torch el bundle es grande). -->

## Requisitos

- Windows 10 u 11 (64-bit)
- Cámara web
- **No** necesitás instalar nada más: no requiere Python ni dependencias

## Cómo se usa

1. Descomprimí el `.zip` en una carpeta (por ejemplo `C:\Recognizer`).
2. Hacé doble clic en **`Recognizer.exe`**.
3. Se abre el **menú** con las aplicaciones; elegí una con el mouse o el teclado.
4. Dentro de cada app, `ESC` o `q` vuelve al menú. Desde el menú, `0` o `Salir` cierra todo.

> **Selector de cámara:** en el encabezado del menú tenés **Detectar** (busca las cámaras
> conectadas, incluidas las del teléfono por enlace móvil) y un botón para rotar entre
> ellas. La cámara elegida se usa en la app que abras.

> **Aviso de Windows:** la primera vez puede aparecer *"Windows protegió tu PC"* porque el
> ejecutable no está firmado. Elegí **Más información → Ejecutar de todas formas**. Es un
> aviso normal en apps independientes.

## Aplicaciones

| # | App | Qué hace |
|---|---|---|
| 1 | **Reconocimiento de gestos** | Controla la PC con la mano: puntero, volumen, música, enlaces y scripts |
| 2 | **Contador de personas** | Cuenta entradas/salidas al cruzar una línea (YOLO + tracking) |
| 3 | **Anti-intrusos** | Avisa con una alerta sonora si alguien entra en una zona |
| 4 | **Postura ergonómica** | Te avisa si te encorvás o adelantás la cabeza (YOLO pose) |
| 7 | **Reconocimiento facial** | Enrolá tu cara y entrá con tu rostro; roles y permisos |
| 5-6 | EPP / Inventario | Próximamente (requieren entrenar un modelo propio) |

## Gestos de mano (app 1)

| Gesto | Acción |
|---|---|
| ☝️ Pointing_Up | Mover el puntero del mouse |
| 👍 Thumb_Up | Subir el volumen |
| 👎 Thumb_Down | Bajar el volumen |
| ✊ Closed_Fist | Silenciar |
| ✋ Open_Palm | Play / Pause |
| ✌️ Victory | Atajo `Ctrl + Shift + M` |
| 🤟 ILoveYou | Abrir el siguiente enlace de tu playlist |
| 👌 OK_Sign | Regla de pinza (se usa en los menús) |

**Menús compuestos:** sosteniendo `Pointing_Up` con la mano izquierda, el gesto de la mano
derecha elige una opción (por ejemplo, saltar el video al 0%, 40% o 70%).

## Reconocimiento facial (app 7)

- **Enrolar**: escribís tu nombre, elegís un rol y la app te guía por **5 ángulos**
  (frente, izquierda, derecha, arriba, abajo) mostrando un marco objetivo para la distancia.
  Se guarda con un ID automático (`F-0001`) en `data/faces/`.
- **Login**: te saluda con `Bienvenido <nombre> <ID>` al reconocerte.
- **Roles**: `admin > operator > viewer`. El **primer rostro enrolado es admin**; el menú
  filtra las apps según tu rol. En modo abierto (`require_login: false`) no hace falta login.
- **Cerrar sesión**: borra la sesión guardada.

Todo el reconocimiento facial corre en CPU con InsightFace y la captura está optimizada para
cámaras lentas (teléfono / enlace móvil) sin retrasos.

## Personalización

Todo se configura en **`config.yaml`**, junto al ejecutable. Se edita con el Bloc de notas y
los cambios se aplican al reabrir la app (no hay que recompilar).

- **Cámara**: `camera.device_index` (0, 1, 2…), resolución y FPS.
- **Apps**: activar/desactivar con `apps.enabled`.
- **Gestos**: umbrales de confianza y estabilidad en `gestures`.
- **Puntero**: zona activa, suavizado y gesto de activación en `pointer`.
- **Acciones**: qué hace cada gesto en `actions.mappings` y `actions.menus`.
- **Contador / anti-intrusos / postura**: línea, zona, tolerancias y alertas.
- **Facial**: `face_auth` (umbral de coincidencia, muestras, `max_inference_fps`, etc.).
- **Tus scripts**: poné archivos `.py`, `.ps1`, `.bat`, `.cmd` o `.sh` en
  `scripts/actions/` y asignálos a un gesto.

## Si algo no funciona

El `.exe` guarda un registro en **`logs/recognizer.log`** (junto al ejecutable) con todo lo
que pasó, incluidos los errores. Es lo primero que conviene mirar.

- **No reconoce gestos**: mejorá la iluminación, acercá la mano y verificá que ninguna otra
  app esté usando la cámara.
- **El puntero no se mueve**: revisá que `pointer.enabled` sea `true` en `config.yaml`.
- **La cámara va lenta (teléfono/enlace móvil)**: en la app facial bajá `det_size` a `320`
  y `max_inference_fps` a `5` (ya son los valores por defecto); en las apps YOLO probá otra
  resolución de cámara.
- **El antivirus lo bloquea**: es un falso positivo típico de apps empaquetadas con
  PyInstaller; podés excluir la carpeta o firmar el ejecutable.

<details>
<summary><b>Opciones avanzadas (línea de comandos, opcional)</b></summary>

La app funciona con doble clic. Estas opciones son solo si querés lanzarla desde una
terminal:

```text
Recognizer.exe --list-apps          # lista las apps del menú y sale
Recognizer.exe --no-gui             # menú de consola en vez de la ventana
Recognizer.exe --device 1           # elige otra cámara
Recognizer.exe --no-actions         # detecta sin ejecutar acciones
Recognizer.exe --no-pointer         # no mueve el cursor
Recognizer.exe --no-browser         # no controla el navegador
Recognizer.exe --no-window --frames 30   # modo headless (para pruebas)
Recognizer.exe --verbose            # registro detallado para calibrar
Recognizer.exe --health-port 8765   # endpoint local para que la web detecte la app
```
</details>

Hecho con Python, MediaPipe, OpenCV, YOLO (Ultralytics) e InsightFace · Licencia MIT
