---
description: Inicia una etapa del roadmap con su rama, su archivo de historial y su plan
agent: build
---

Inicia la etapa: $ARGUMENTS

Pasos obligatorios:
1. Lee `docs/STATE.md` y `docs/history/index.md`. Abre el historial de otra etapa SOLO si
   esta etapa depende de sus decisiones.
2. Actualiza `docs/STATE.md` (fase en curso, rama).
3. Delega en `git-ops`: crear `stage/<n>-<slug>` desde `dev` y confirmar la rama actual.
4. Crea `docs/history/stage-<n>-<slug>.md` con la plantilla de `docs/WORKFLOW.md`
   (objetivo, criterios de aceptación, plan).
5. Crea la lista de tareas (todowrite) y ejecuta con `vision-dev` y `test-writer`.
6. Al terminar la implementación y los tests, continúa con `/stage-review`.
