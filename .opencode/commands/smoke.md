---
description: Prueba rápida de la cámara real (mide FPS sin abrir ventana)
agent: build
---

Ejecuta `uv run smoke --frames 30 --no-window` y reporta: FPS medio, fotogramas contados y
cualquier error. Si falla, revisa `config.yaml` (device_index) y que la cámara no esté en
uso por otra aplicación.
