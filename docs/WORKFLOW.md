# Flujo de trabajo por etapas

Cada etapa del roadmap se ejecuta con roles especializados y deja rastro verificable.
Objetivo: calidad y bajo consumo de tokens. El estado vivo vive en un único archivo
pequeño (`docs/STATE.md`); el detalle vive en `docs/history/` y se lee solo cuando hace falta.

## Roles

| Rol | Quién | Responsabilidad |
|---|---|---|
| Orquestador | agente principal | planifica la etapa, delega, decide y actualiza el estado |
| Implementación | subagente `vision-dev` | código de producción en `src/` |
| Tests | subagente `test-writer` | tests en `tests/` y ejecución del gate |
| Revisión | subagente `reviewer` | revisión independiente (no edita) |
| Documentación | subagente `docs-writer` | README, `docs/`, STATE e history |
| Git | subagente `git-ops` | ramas, commits, merge a dev, push |

Regla: cada subagente hace una sola cosa. No se pide a un agente que haga tests y git a la vez.

## Estado vs historial (manejo de tokens)

- `docs/STATE.md` (<= 50 líneas): fase actual, rama, hecho, siguiente, bloqueos.
  Se carga siempre como instrucción; es la primera lectura de cualquier sesión.
- `docs/history/index.md`: tabla resumen de todas las etapas (una línea por etapa).
- `docs/history/stage-N-slug.md`: detalle de una sola etapa. Se lee únicamente si la etapa
  actual depende de decisiones de esa etapa. Nunca leer todo el historial.
- Los reportes de subagentes: máximo 10 líneas.

## Ciclo de una etapa

1. **Inicio** (`/stage-start N-slug`)
   - Leer `docs/STATE.md` y `docs/history/index.md`.
   - `git-ops`: `git checkout dev`, `git pull` si hay remoto, `git checkout -b stage/N-slug`.
   - Crear `docs/history/stage-N-slug.md` con la plantilla de abajo.
   - Definir criterios de aceptación y lista de tareas (todowrite).
2. **Implementación**
   - `vision-dev` implementa respetando `AGENTS.md` y `docs/ARCHITECTURE.md`.
   - Cambios atómicos; si hace falta, `git-ops` commitea por bloques a pedido del orquestador.
3. **Tests**
   - `test-writer` agrega tests; lo que use hardware real se marca `@pytest.mark.integration`.
   - Gate obligatorio: `uv run lint`, `uv run typecheck`, `uv run test`, `uv run check-arch`.
4. **Revisión** (`/stage-review`)
   - `reviewer` revisa contra `AGENTS.md` y `docs/ARCHITECTURE.md` y reporta hallazgos
     `severidad | archivo:línea | problema | sugerencia`.
   - Hallazgos bloqueantes: corregir con `vision-dev`/`test-writer` y repetir el gate.
5. **Documentación**
   - `docs-writer` completa el history de la etapa y actualiza `docs/STATE.md`
     (fase siguiente, decisiones, bloqueos).
6. **Cierre** (`/stage-finish`)
   - `git-ops`: commits de la etapa en `stage/N-slug`, `git checkout dev`,
     `git merge --no-ff stage/N-slug`, `git push origin dev`.
   - `main` no se toca nunca localmente; el usuario mergea `dev -> main` en GitHub.
7. **Siguiente etapa**: repetir el ciclo.

## Etapas de apps del launcher (etapa 10a+)

Cada app nueva se implementa como una etapa propia (y se subdivide en fases `a/b/c` si es
grande, p. ej. `stage/10b-people-counter-deteccion`). Checklist obligatorio de una app:

1. **Catalogo**: agregar/activar su `AppInfo` en `core/domain/app.py`
   (`implemented=True` cuando exista). Mantener el orden acordado en
   `docs/ROADMAP.md`: implementadas, luego faciles (sin entrenamiento),
   intermedias, OCR al final y entrenamiento al ultimo.
2. **Runner**: crear `cli/apps/<app>.py` con una funcion `run_<app>(request, ...) -> int`
   que respete `AppRunRequest`. Registrar la rama en `cli/menu.resolve_runner` con **import
   perezoso** (la app no se carga hasta que se selecciona).
3. **Salida al menú**: `ESC`/`q` termina la app y vuelve al menú; nunca cerrar el proceso.
4. **Modularidad**: la app importa solo sus dependencias; nada de cargar modelos de otras
   apps. Una sola vía de inferencia por app (sin detector de respaldo que reprocese el frame).
5. **Puertos y adaptadores**: la lógica pura va en `core` (p. ej. conteo, reglas de ángulo);
   la inferencia y los efectos van en `adapters` (YOLO, OpenCV, red, persistencia).
6. **Config**: umbrales y mapeos en `config.yaml` (seccion propia por app) y modelos
   pydantic en `core/config.py`; defaults en `core/constants.py`.
7. **Tests y gate**: tests unitarios con dobles (sin hardware) + `@pytest.mark.integration`
   para cámara; gate completo verde y medición de FPS (`uv run smoke`) registrada en el
   history de la etapa.
8. **Sin entrenamiento primero**: las 8 apps sin entrenamiento van antes que
   las que requieren entrenar (EPP, inventario). Detalle y prioridades en
   `docs/ROADMAP.md`; facial ya esta implementado y no bloquea.

## Plantilla de history de etapa

```md
# Etapa N — Título

- **Rama:** stage/N-slug
- **Estado:** en curso | completada
- **Objetivo:** qué se quiere lograr
- **Criterios de aceptación:** lista verificable

## Plan
## Cambios (archivos)
## Decisiones
## Tests y gate (resultados reales)
## Revisión (hallazgos y correcciones)
## Commits
## Pendientes / riesgos
```

## Reglas de oro

- Sin gate verde no hay merge.
- Sin revisión no hay cierre de etapa.
- Toda decisión relevante queda escrita (history o STATE), no solo en el chat.
- No leer historial completo ni volcar archivos enteros en los reportes.
- Los subagentes no piden permisos: trabajan de forma autónoma y reportan.
