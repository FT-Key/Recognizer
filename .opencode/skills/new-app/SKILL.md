---
name: new-app
description: Úsala SOLO al crear o habilitar una aplicación del launcher de Recognizer (menú, runner de app, YOLO/postura/conteo/facial). Dispara con "app", "menú", "launcher", "YOLO", "contador", "postura", "EPP", "inventario", "facial".
---

# Añadir una aplicación al launcher

1. **Catalogo (dominio puro)**: en `core/domain/app.py` agrega el `AppId` y su `AppInfo`
   (título, descripción, `implemented`, `preparation`). Al terminarla, pon
   `implemented=True` y respeta el orden acordado (gestos; sin entrenamiento; con
   entrenamiento/enrolamiento).
2. **Runner (imperative shell)**: crea `cli/apps/<app>.py` con
   `def run_<app>(request: AppRunRequest, *, ...) -> int`. Usa `cli/runtime.run_camera_loop`
   y los adaptadores; no metas lógica pura aquí (esa va a `core`).
3. **Registro perezoso**: agrega la rama en `cli/menu.resolve_runner` con el import dentro
   del `match`. Nunca importes la app a nivel de modulo del menú: abrir el menú no debe
   cargar MediaPipe/YOLO ni abrir la cámara.
4. **Salida al menú**: la app termina con `ESC`/`q` y devuelve el control; no llames a
   `sys.exit` ni destruyas recursos del launcher.
5. **Puertos/adaptadores**: si entra una librería nueva (p. ej. `ultralytics`), define el
   `Protocol` en `core/ports/`, implementa el adaptador en `adapters/` y añade la librería a
   `forbidden_modules` del contrato "core no depende de infraestructura" en `pyproject.toml`.
6. **Config**: sección propia en `config.yaml` + modelo pydantic en `core/config.py`;
   defaults en `core/constants.py`. Cero números mágicos.
7. **Rendimiento**: una sola vía de inferencia por app (sin fallback que reprocese el mismo
   frame); carga perezosa de modelos; mide FPS con `uv run smoke --frames 30 --no-window` y
   regístralo en el history de la etapa.
8. **Tests**: unitarios con dobles/fakes (sin hardware) para la lógica del core y el
   despacho del menú; `@pytest.mark.integration` para cámara. Gate completo antes de cerrar.
9. **Empaquetado**: si la app trae una dependencia pesada, actualiza
   `packaging/recognizer.spec` (collect) y verifica el `.exe`.

Referencia viva: la app de gestos (`cli/app.py:run_gestures`) y su rama en
`cli/menu.py:resolve_runner`.
