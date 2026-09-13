---
description: Cierra la etapa: documenta resultados, merge --no-ff a dev y push del remoto
agent: build
---

Cierra la etapa actual:
1. Verifica que el gate esté verde; si no, usa `/stage-review` primero.
2. Delega en `docs-writer`: completar `docs/history/stage-<n>-<slug>.md`,
   actualizar `docs/history/index.md` y `docs/STATE.md` (estado final y siguiente etapa).
3. Delega en `git-ops`: commits de la etapa en `stage/<n>-<slug>`, `git checkout dev`,
   `git merge --no-ff`, `git push origin dev`.
4. Confirma que `main` NO fue tocado.
5. Reporta: rama, commits, resultado del push y siguiente etapa.
