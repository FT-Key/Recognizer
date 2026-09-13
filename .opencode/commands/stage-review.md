---
description: Revisión de calidad, tests y arquitectura de la etapa actual antes del merge
agent: build
---

Ejecuta la revisión de la etapa actual:
1. Corre el gate completo: `uv run lint`, `uv run typecheck`, `uv run test`,
   `uv run check-arch`.
2. Delega en `reviewer` una revisión independiente con hallazgos `archivo:línea`.
3. Corrige los hallazgos bloqueantes con `vision-dev`/`test-writer` y repite el gate
   hasta que esté verde.
4. Registra el resultado de la revisión en `docs/history/stage-<n>-<slug>.md`.
5. Si el veredicto es "apto para merge", continúa con `/stage-finish`.
