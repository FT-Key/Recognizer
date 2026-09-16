# Empaquetado de Recognizer (escritorio) con PyInstaller

**Estado:** implementado
**Herramienta:** PyInstaller 6.x
**Plataforma objetivo:** Windows (64-bit); el flujo es válido en Linux/macOS con el
binario de esa plataforma.

---

## Qué genera

```bash
uv run python scripts/build_exe.py
```

Produce la carpeta `dist/Recognizer/`:

```
dist/Recognizer/
├── Recognizer.exe        # ejecutable principal (arranque rápido)
├── config.yaml           # EDITABLE por el usuario
├── models/               # EDITABLE: modelos MediaPipe (.task)
│   ├── gesture_recognizer.task
│   ├── hand_landmarker.task
│   └── blaze_face_short_range.tflite
├── scripts/actions/      # EDITABLE: scripts de usuario
└── _internal/            # dependencias (Python, DLLs, mediapipe, cv2, matplotlib)
                          # NO tocar
```

**Tamaño aproximado:** ~280-350 MB (MediaPipe + OpenCV + matplotlib + numpy).
Se distribuye comprimiendo `dist/Recognizer/` en un `.zip`; el usuario final
descomprime y ejecuta `Recognizer.exe` (no necesita Python ni `uv`).

---

## Publicar una release (GitHub Releases)

La web enlaza el botón "Descargar para Windows" a
`https://github.com/FT-Key/Recognizer/releases/latest` (siempre la última release).

```powershell
# 1. Compilar (genera dist/Recognizer/)
uv run python scripts/build_exe.py

# 2. Sacar la carpeta logs (la crea el .exe al correr) y comprimir
Remove-Item -Recurse -Force dist\Recognizer\logs -ErrorAction SilentlyContinue
Compress-Archive -Path dist\Recognizer -DestinationPath dist\Recognizer-v0.1.0-win64.zip
```

3. En GitHub: **Releases → Draft a new release**.
   - Tag: `v0.1.0` (crear el tag nuevo).
   - Target: `main` (o `dev` si todavía no se mergeó).
   - Título y descripción (usar el Markdown con el logo del repo).
   - **Attach binaries**: subir el `.zip`.
   - Marcar **Set as the latest release** y publicar.

Notas:
- El `.zip` **no** va al repositorio (git bloquea archivos > 100 MB); va como *asset* de
  la release, que admite hasta 2 GB por archivo.
- El logo para la descripción sale del repo:
  `https://raw.githubusercontent.com/FT-Key/Recognizer/main/web/public/logo.png`.
- El `.exe` no está firmado: Windows muestra "Windows protegió tu PC" la primera vez.
- Al publicar una versión nueva, el botón de la web apunta sola a la última (no hay que
  tocar el código).

---

## Cómo funciona PyInstaller (resumen)

PyInstaller **congela** el intérprete de Python y todas las dependencias dentro de la
carpeta de distribución:

1. **Analysis**: recorre las importaciones del punto de entrada
   (`packaging/entrypoint.py`) y construye el grafo de módulos. Los imports dinámicos
   (los que MediaPipe hace por ruta) no se detectan solos: por eso el `.spec` usa
   `collect_all("mediapipe")` y `collect_submodules("pynput")`.
2. **PYZ**: empaqueta el bytecode de los módulos Python en un archivo comprimido.
3. **EXE**: crea el *bootloader* (un ejecutable en C) que arranca Python embebido.
4. **COLLECT**: copia binarios nativos (`.dll`, `.pyd`) y datos a `_internal/`.

### onedir vs onefile

Usamos **onedir** (carpeta), no `--onefile`:

| | onedir | onefile |
|---|---|---|
| Arranque | Rápido (~1 s) | Lento (extrae a temporal, 5-15 s) |
| MediaPipe | Estable | Riesgo con `.task` memory-mapped |
| Distribución | Carpeta `.zip` | Un solo `.exe` |

MediaPipe carga DLLs nativas y **memory-mapea** los modelos `.task`; con `onefile`
PyInstaller extrae todo a un directorio temporal en cada arranque, lo que es lento e
inestable. `onedir` evita ese problema.

### Recursos editables (config y modelos)

`config.yaml`, `models/` y `scripts/actions/` **no se incrustan**: se copian junto al
`.exe` desde `scripts/build_exe.py`. Así el usuario puede cambiar umbrales, modelos o
scripts sin recompilar.

### Resolución de rutas cuando está empaquetado

`sys.frozen` es `True` dentro del `.exe`. `cli/app.py` detecta ese caso y:

- resuelve `--config` relativo a la carpeta del ejecutable (`Path(sys.executable).parent`);
- cambia el directorio de trabajo a la carpeta de la config para que las rutas
  relativas del YAML (`models/gesture_recognizer.task`, `scripts/actions/...`) se
  resuelvan sin tocar la configuración.

Así funciona aunque se lance el `.exe` desde otra carpeta.

---

## Endpoint de salud (detección desde la web)

El `.exe` arranca por defecto un servidor local de salud en `127.0.0.1:8765`
(`--health-port 8765`; en desarrollo el default es `0`, desactivado). La app web lo
sondea para mostrar el banner "Abrir app" en lugar de "Descargar app".

```bash
Recognizer.exe --health-port 8765     # activa el endpoint (default en el .exe)
Recognizer.exe --health-port 0        # lo desactiva
```

El endpoint expone solo `GET /health` en loopback:
`{"app":"recognizer","version":"0.1.0","status":"ok","api":1}`.

---

## Archivos del empaquetado

| Archivo | Rol |
|---|---|
| `packaging/entrypoint.py` | Punto de entrada (llama a `recognizer.cli.app.main`). |
| `packaging/recognizer.spec` | Receta de PyInstaller (Analysis/PYZ/EXE/COLLECT). |
| `scripts/build_exe.py` | Compila y copia config/models/scripts junto al `.exe`. |
| `src/recognizer/adapters/health_server.py` | Servidor de salud local (adaptador). |

---

## Logs

El `.exe` escribe un log en `dist/Recognizer/logs/recognizer.log` (junto al ejecutable).
Incluye arranque, config, pantalla detectada, servidor de salud, carga del modelo y
**cualquier excepción no controlada** (con traza completa). Si la carpeta del ejecutable
no es escribible, cae al directorio temporal del sistema.

```bash
Recognizer.exe                          # log por defecto en logs/recognizer.log
Recognizer.exe --verbose                # además DEBUG
Recognizer.exe --log-file C:\ruta\mio.log
```

Ejemplo de arranque correcto en el log:

```
INFO recognizer.app: Pantalla detectada: 1920x1080
INFO recognizer.health: Servidor de salud en http://127.0.0.1:8765/health
INFO recognizer.app:   OK Cargando modelo de gestos (4638 ms)
```

## Notas y solución de problemas

- **`ModuleNotFoundError: matplotlib`**: `mediapipe.tasks.python.vision.drawing_utils`
  importa matplotlib a nivel de módulo. No excluir matplotlib en el `.spec`.
- **`ModuleNotFoundError: tkinter`**: `pynput_mouse._default_screen_size()` importa
  tkinter para resolver el tamaño de pantalla del puntero. Si se excluye tkinter, el
  gesto `Pointing_Up` lanza un error y **cierra la app**. No excluir tkinter.
- **La app se cierra sola**: revisa `logs/recognizer.log`; la última traza indica la
  causa. El bucle de cámara ya no se tumba por un fallo de acción o de puntero (se
  registra y continúa).
- **Primer arranque lento**: matplotlib inicializa su `fontManager` (~10 s) la primera
  vez. Es un coste único.
- **Modelos faltantes**: si `models/` está vacío, ejecuta
  `uv run python scripts/download_models.py` antes de empaquetar.
- **Recompilar**: `scripts/build_exe.py` usa `--clean`, así que cada build es limpio.
- **Antivirus**: algunos antivirus marcan falsos positivos con PyInstaller; firmar el
  `.exe` o excluir la carpeta lo mitiga.

---

## Verificación

```bash
# 1. Compilar
uv run python scripts/build_exe.py

# 2. Ayuda (desde otra carpeta para probar la resolución de rutas)
dist/Recognizer/Recognizer.exe --help

# 3. Ejecución headless
dist/Recognizer/Recognizer.exe --no-window --frames 30

# 4. Endpoint de salud
dist/Recognizer/Recognizer.exe --no-window --frames 400 --health-port 8765
curl http://127.0.0.1:8765/health
```
