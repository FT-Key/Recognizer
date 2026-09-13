# Arquitectura

## Visión general

Hexagonal (puertos y adaptadores) + pipeline de frames + EventBus tipado in-process.
El núcleo (`core`) no conoce frameworks ni sistema operativo; los adaptadores implementan
los puertos; `bootstrap`/CLI son el composition root (inyección por constructor).

```
frame -> [HandPipeline] -> GestureStabilizer -> EventBus -> ActionSink (decoradores)
```

## Capas y contrato de dependencias

- `core/domain`: vocabulario (enums), objetos de valor (`Frame`), eventos frozen, acciones.
- `core/ports`: Protocols que el núcleo necesita (`FrameSource`, `HandTracker`, `EventBus`...).
- `core/pipeline`: processors + `PipelineBuilder` (pipes & filters).
- `adapters/`: OpenCV, MediaPipe, pynput, subprocess, persistencia, red (futuro).
- `settings.py`, `bootstrap.py`, `cli/`: composición y entrada.
- Contratos verificados por import-linter en `pyproject.toml`: el core no importa capas
  externas ni infraestructura; los adapters no importan cli/settings.

## Ejes de cambio previstos (justifican las abstracciones)

1. Fuente de frames: cámara local -> stream web.
2. Destino de acciones: local (SO) -> red/remoto.
3. Identidad: sin enrolamiento -> rol/perfil con permisos.
4. Persistencia: ninguna -> embeddings de rostro / dataset de gestos.
5. Interfaz: overlay OpenCV -> UI de escritorio -> web.

## Patrones y regla de admisión

| Patrón | Uso real en el proyecto | Eje |
|---|---|---|
| Strategy | `GestureClassifier`, `PointerSmoothing`, `PolicyEngine` | 1,2,3 |
| Factory | `PipelineFactory` / `ActionFactory` desde config | 1,2 |
| Adapter | Puertos hacia MediaPipe/OpenCV/pynput/subprocess/red | 1,2 |
| Repository | Embeddings/dataset (solo cuando existan) | 4 |
| DI | Inyección por constructor + composition root | todos |
| Observer | `EventBus` tipado in-process | 1,2,5 |
| Decorator | `Gated(Debounced(Logged(action)))`, `ConfidenceFilter` | 2,3 |
| Facade | `RecognizerApp`, `MediaPipeTasksFacade` | todos |
| Builder | `PipelineBuilder` (uno solo) | 1 |
| Command | `Action` con parámetros y `execute(ctx)` | 2 |
| Null Object | `AllowAllIdentity`, `NoOpAction` (MVP sin roles) | 3 |

**Regla de admisión:** un patrón entra solo si (a) hay 2+ implementaciones reales o
previstas en el roadmap, (b) aísla una dependencia externa, o (c) los tests necesitan un
doble. Si no cumple: código directo, sin interfaz.
**Prohibidos por defecto:** Singleton, AbstractFactory, broker externo de eventos,
Repository para config, herencia mayor a un nivel, capas sin eje de cambio.

## Prácticas obligatorias

- Enums y constantes centrales (`core/constants.py`, `core/domain`); nada de strings o
  números mágicos en el código que los usa; umbrales y mapeos en `config.yaml`.
- Cero `typing.Any` en código propio (`mypy --strict` + ANN401). Fronteras con librerías
  externas vía `Protocol` + `cast` documentado.
- Dataclasses `frozen=True` para eventos y objetos de valor; `match/case` para despacho;
  argumentos keyword-only en APIs con más de un parámetro.
- Errores del dominio en `core/errors.py`; sin `except` desnudos; recursos con context managers.
- Functional core / imperative shell: la lógica no tiene efectos; los efectos viven en
  `adapters/`.

## Gate

`uv run lint` · `uv run typecheck` · `uv run test` (cobertura >= 80%) ·
`uv run check-arch` · `uv run smoke --frames 30 --no-window`.

## Futuro web

Ver `docs/WEB-PLAN.md`. El core se reutiliza como librería; el servidor web será otro
adaptador (`FrameSource` por WebSocket/WebRTC, `ActionSink` remoto).
