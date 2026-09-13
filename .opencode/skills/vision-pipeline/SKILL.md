---
name: vision-pipeline
description: Úsala SOLO al añadir o modificar processors/pipelines de visión en Recognizer (MediaPipe landmarks, clasificación de gestos, suavizado, overlay). Dispara con "processor", "pipeline", "landmarks", "overlay", "estabilizador".
---

# Añadir un processor de visión

1. La interfaz (Protocol) vive en `core/ports/` o `core/pipeline/`; la implementación con
   MediaPipe/OpenCV vive en `adapters/`. El core nunca importa esas librerías.
2. Un processor = una responsabilidad. Entrada/salida tipadas (`Frame`, landmarks, eventos
   del dominio); nada de estado global ni de efectos internos.
3. Parámetros (umbrales, N de estabilización, resolución) SIEMPRE desde `config.yaml` a
   través de modelos pydantic en `core/config.py`; los defaults van en `core/constants.py`.
4. Vocabulario con enums en `core/domain/` (p. ej. `GestureName`); nunca strings sueltos.
5. Tests unitarios con landmarks sintéticos (fixtures); los tests de cámara real van con
   `@pytest.mark.integration`.
6. Mide FPS antes y después (`uv run smoke --frames 30 --no-window`) y registra el impacto
   en el history de la etapa. Objetivo actual: >= 20 FPS con 2 manos a 640x480 en CPU.
